from __future__ import annotations

from importlib import import_module
from typing import Any

from .base import BaseExtractor, ExtractorResult, NoExtractorError
from .extractor import Extractor

_LAZY_PROVIDER_MODULES = {
    "PaddleOCRExtractor": ".paddle_ocr",
    "RapidOCRExtractor": ".rapid_ocr",
    "UnlimitedOCRExtractor": ".unlimited_ocr",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_PROVIDER_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "BaseExtractor",
    "Extractor",
    "ExtractorResult",
    "NoExtractorError",
    "PaddleOCRExtractor",
    "RapidOCRExtractor",
    "UnlimitedOCRExtractor",
]
