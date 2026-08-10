from __future__ import annotations

import asyncio
import csv
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd


class ExcelParser:
    name = "excel"

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        encoding: str = "utf-8-sig",
        delimiter: str | None = None,
        sheets: Sequence[str] | None = None,
    ) -> str:
        is_excel, data = await _parse_table_data(
            file_source,
            file_name=file_name,
            encoding=encoding,
            delimiter=delimiter,
            sheets=sheets,
        )
        return _tables_markdown(is_excel, data)

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        encoding: str = "utf-8-sig",
        delimiter: str | None = None,
        sheets: Sequence[str] | None = None,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        is_excel, data = await _parse_table_data(
            file_source,
            file_name=file_name,
            encoding=encoding,
            delimiter=delimiter,
            sheets=sheets,
        )
        if as_json:
            return {"tables": data}
        return _tables_markdown(is_excel, data)


async def _parse_table_data(
    file_source: str | Path | bytes | BinaryIO,
    *,
    file_name: str,
    encoding: str,
    delimiter: str | None,
    sheets: Sequence[str] | None,
) -> tuple[bool, list[dict[str, object]]]:
    is_excel, tables = await asyncio.to_thread(
        _read_tables,
        file_source,
        file_name,
        encoding,
        delimiter,
        list(sheets) if sheets is not None else None,
    )
    return is_excel, [_table_data(name, frame) for name, frame in tables.items()]


def _tables_markdown(
    is_excel: bool,
    tables: list[dict[str, object]],
) -> str:
    return "\n\n".join((f"## {table['name']}\n\n{_markdown_table(table)}" if is_excel else _markdown_table(table)).rstrip() for table in tables)


def _read_tables(
    file_source: str | Path | bytes | BinaryIO,
    file_name: str,
    encoding: str,
    delimiter: str | None,
    sheets: list[str] | None,
) -> tuple[bool, dict[str, Any]]:
    suffix = Path(file_name).suffix.lower()
    source = _table_source(file_source)
    if suffix == ".csv":
        try:
            frame = pd.read_csv(
                source,
                encoding=encoding,
                sep=delimiter or _detect_delimiter(source, encoding),
                keep_default_na=False,
            )
        except pd.errors.EmptyDataError:
            frame = pd.DataFrame()
        return False, {Path(file_name).stem: frame}
    if suffix == ".xlsx":
        return True, pd.read_excel(
            source,
            sheet_name=sheets,
            keep_default_na=False,
        )
    raise ValueError(f"Unsupported table file: {suffix}")


def _table_source(
    file_source: str | Path | bytes | BinaryIO,
) -> Path | BytesIO:
    if isinstance(file_source, (str, Path)):
        return Path(file_source)
    if isinstance(file_source, bytes):
        return BytesIO(file_source)

    content = file_source.read()
    if not isinstance(content, bytes):
        raise TypeError("file_source.read() 必须返回 bytes。")
    return BytesIO(content)


def _detect_delimiter(source: Path | BytesIO, encoding: str) -> str:
    if isinstance(source, Path):
        with source.open(encoding=encoding, newline="") as file:
            sample = file.read(8192)
    else:
        position = source.tell()
        sample = source.read(8192).decode(encoding)
        source.seek(position)
    if not sample:
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _table_data(name: str, frame: Any) -> dict[str, object]:
    return {
        "name": name,
        "headers": [str(column) for column in frame.columns],
        "rows": frame.to_numpy().tolist(),
    }


def _markdown_table(table: dict[str, object]) -> str:
    headers = table["headers"]
    rows = table["rows"]
    if not headers:
        return ""

    def line(values: object) -> str:
        return (
            "| "
            + " | ".join(
                str(value).replace("|", "\\|")
                for value in values  # type: ignore[union-attr]
            )
            + " |"
        )

    return "\n".join(
        [
            line(headers),
            line(["---"] * len(headers)),  # type: ignore[arg-type]
            *(line(row) for row in rows),  # type: ignore[union-attr]
        ]
    )
