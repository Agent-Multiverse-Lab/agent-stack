from typing import Any

from pydantic import BaseModel


class ToolArgumentItem(BaseModel):
    name: str
    type: str
    description: str
    required: bool


class ToolCatalogItem(BaseModel):
    slug: str
    name: str
    description: str
    metadata: dict[str, Any]
    args: list[ToolArgumentItem]
    category: str
    tags: list[str]
    icon: str
    config_guide: str


class ToolCatalogResponse(BaseModel):
    success: bool = True
    data: list[ToolCatalogItem]


class ToolOptionItem(BaseModel):
    label: str
    value: str


class ToolOptionsResponse(BaseModel):
    success: bool = True
    data: list[ToolOptionItem]
