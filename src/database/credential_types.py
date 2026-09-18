import json

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON, Text
from sqlalchemy.types import TypeDecorator


def credential_cipher() -> Fernet:
    from src.configs import config

    try:
        return Fernet(config.model_credential_key.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeError):
        raise RuntimeError("未配置有效的 MODEL_CREDENTIAL_KEY") from None


def encrypt_credential(value: str) -> str:
    return "enc:v1:" + credential_cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_credential(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("enc:v1:"):
        raise RuntimeError("模型凭据尚未完成加密迁移")
    try:
        return credential_cipher().decrypt(value[7:].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError):
        raise RuntimeError("模型凭据解密失败") from None


class EncryptedCredential(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_credential(value) if value else ""

    def process_result_value(self, value, dialect):
        return decrypt_credential(value) if value else ""


class EncryptedHeaders(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_credential(json.dumps(value, ensure_ascii=False)) if value else {}

    def process_result_value(self, value, dialect):
        return json.loads(decrypt_credential(value)) if value else {}
