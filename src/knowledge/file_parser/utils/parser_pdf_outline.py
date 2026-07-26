from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

from pypdf import PdfReader

from src.utils.logger import logger


def extract_pdf_outline(
    file_source: str | bytes | Path | BinaryIO,
) -> list[tuple[str, int, int]]:
    """
    提取 PDF 文件的目录结构（大纲）。

    :param file_source: PDF 文件的路径、字节流或文件名。
    :return: 包含目录结构的列表，每个条目是一个元组，包含标题、深度和页码。
    """
    current_file_source: Path | BytesIO
    if isinstance(file_source, (str, Path)):
        current_file_source = Path(file_source)
    elif isinstance(file_source, bytes):
        current_file_source = BytesIO(file_source)
    else:
        file_source.seek(0)
        content = file_source.read()
        if not isinstance(content, bytes):
            raise TypeError("PDF file_source 文件流必须返回 bytes。")
        current_file_source = BytesIO(content)

    try:
        with PdfReader(current_file_source) as pdf:
            file_outline: list[tuple[str, int, int]] = []

            def dfs(nodes: list[Any], depth: int) -> None:
                for node in nodes:
                    if isinstance(node, list):
                        dfs(node, depth + 1)
                        continue

                    page_index = pdf.get_destination_page_number(node)
                    if page_index is None:
                        continue
                    file_outline.append(
                        (
                            str(node["/Title"]),
                            depth,
                            page_index + 1,
                        )
                    )

            dfs(pdf.outline, 0)
            return file_outline
    except Exception as error:
        logger.exception("提取 PDF 大纲失败: %s", error)
        return []
