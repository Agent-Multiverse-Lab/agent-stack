import asyncio
import mimetypes
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from minio import Minio
from minio.error import S3Error

from src.configs.config import config
from src.utils.logger import logger

DEFAULT_CONTENT_TYPE = "application/octet-stream"
_storage_instance: "MinioStorage | None" = None
_unsafe_filename_pattern = re.compile(r"[^A-Za-z0-9._-]+")

PUBLIC_BUCKET_KEY = {"public"}


@dataclass(slots=True)
class MinIOUploadResult:
    object_url: str
    bucket_name: str
    object_name: str


def sanitize_filename(filename: str) -> str:
    """将文件名转换为适合存储的 ASCII 名称。"""
    normalized = (
        unicodedata.normalize("NFKD", filename or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    sanitized = _unsafe_filename_pattern.sub("_", normalized).strip("._")
    return sanitized or "file"


def build_object_name(conversation_id: str | int, category: str, filename: str) -> str:
    """构建唯一的文件存储路径。"""
    safe_filename = sanitize_filename(filename)
    now = datetime.now(UTC)
    folder = "images" if category == "image" else "documents"
    return f"conversations/{conversation_id}/{folder}/{now:%Y}/{now:%m}/{uuid4()}_{safe_filename}"


class MinioStorage:
    """MinIO 文件存储管理器。"""

    def __init__(self) -> None:
        self.minio_endpoint = config.minio_endpoint
        self.minio_access_key = config.minio_access_key
        self.minio_secret_key = config.minio_secret_key
        self._client: Minio | None = None

    def get_client(self) -> Minio:
        """获取懒加载初始化的 MinIO 客户端。"""
        if self._client is None:
            self._client = Minio(
                endpoint=self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                secure=False,
            )
        return self._client

    def _check_buckets_accessabe(self, bucket_name: str):
        if bucket_name not in PUBLIC_BUCKET_KEY:
            return

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                }
            ],
        }
        self._client.set_bucket_policy(bucket_name=bucket_name, policy=policy)

    def _check_file_type(self, object_name: str) -> str:
        object_type, _ = mimetypes.guess_type(object_name)
        if object_type:
            return object_type

        object_suffix = object_name.split(".")[-1].lower()

        object_type_collection = {
            "md": "text/markdown",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "zip": "application/zip",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "tif": "image/tiff",
            "png": "image/png",
            "jpg": "image/jpg",
            "tiff": "image/tiff",
        }
        return object_type_collection.get(object_suffix, "application/octet-stream")

    def check_buckets_status(self, bucket_name: str) -> None:
        """确保指定存储桶存在。"""
        flag = False
        self.get_client()
        if not self._client.bucket_exists(bucket_name):
            self._client.make_bucket(bucket_name)
            flag = True
            logger.info(f"buket name:{bucket_name} 已创建")
        self._check_buckets_accessabe(bucket_name)

        if bucket_name in PUBLIC_BUCKET_KEY and flag:
            logger.info(f"buket name:{bucket_name} 可访问")

    def check_file_exist(self, bucket_name: str, object_name: str) -> bool:
        client = self.get_client()
        return bool(
            client.stat_object(
                bucket_name=bucket_name,
                object_name=object_name,
            )
        )

    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        content_data: bytes,
        content_type: str | None = None,
    ) -> MinIOUploadResult:
        """上传文件内容到存储。"""

        self.check_buckets_status(bucket_name)

        object_type = content_type or self._check_file_type(object_name)
        content_data_stream = BytesIO(content_data)
        result = self._client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=content_data_stream,
            length=len(content_data),
            content_type=object_type,
        )

        assert result is not None

        object_url = f"http://{self.minio_endpoint}/{bucket_name}/{object_name}"

        return MinIOUploadResult(
            object_url=object_url, bucket_name=bucket_name, object_name=object_name
        )

    async def aupload_file(
        self,
        bucket_name: str,
        object_name: str,
        content_data: bytes,
        content_type: str | None = None,
    ) -> MinIOUploadResult:
        """upload的异步方法"""
        kwargs = {
            "bucket_name": bucket_name,
            "object_name": object_name,
            "content_data": content_data,
            "content_type": content_type,
        }
        return await asyncio.to_thread(self.upload_file, **kwargs)

    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """从存储中删除文件。"""
        client = self.get_client()
        client.remove_object(bucket_name=bucket_name, object_name=object_name)
        logger.info(f"bucket:{bucket_name} 下的文件:{object_name} 已删除")
        return True

    async def adelete_file(self, bucket_name: str, object_name: str) -> bool:
        """异步删除方案"""
        result = await asyncio.to_thread(
            self.delete_file, bucket_name=bucket_name, object_name=object_name
        )
        return result

    async def create_file_access_url(self, bucket_name: str, object_name: str) -> str:
        """创建临时文件访问 URL。"""
        client = self.get_client()
        try:
            return await run_in_threadpool(
                client.presigned_get_object,
                bucket_name,
                object_name,
                expires=timedelta(seconds=600),
            )
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="创建文件访问 URL 失败。",
            ) from exc

    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """下载文档"""
        client = self.get_client()
        result = client.get_object(
            bucket_name=bucket_name, object_name=object_name
        )
        data = result.read()
        result.close()
        logger.info(f"{bucket_name} 下的：{object_name}，已下载")
        return data

    async def adownload_file(self, bucket_name: str, object_name: str) -> bytes:
        """从存储下载文件内容。"""

        data = await asyncio.to_thread(
            self.download_file, bucket_name=bucket_name, object_name=object_name
        )
        return data

    async def delete_file_by_prefix(
        self,
        bucket_name: str,
    ):
        pass


def get_storage() -> MinioStorage:
    """获取单例存储管理器。"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MinioStorage()
    return _storage_instance
