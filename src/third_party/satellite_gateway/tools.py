"""LangChain tools backed by the satellite catalog gRPC client."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from src.configs import config as sys_config

from .client import SatelliteGatewayClient, SatelliteGatewayError


class SatelliteToolContext(Protocol):
    gateway_target: str
    gateway_project_id: str
    gateway_timeout_seconds: float
    uid: str
    run_id: str


class SceneSearchInput(BaseModel):
    bbox: list[float] = Field(
        min_length=4,
        max_length=4,
        description="WGS84 [west, south, east, north]",
    )
    acquired_from: str = Field(description="RFC3339 inclusive start time")
    acquired_to: str = Field(description="RFC3339 exclusive end time")
    source_ids: list[str] = Field(default_factory=list)
    collection_ids: list[str] = Field(default_factory=list)
    satellites: list[str] = Field(default_factory=list)
    sensors: list[str] = Field(default_factory=list)
    processing_levels: list[str] = Field(default_factory=list)
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=50)


class SceneInspectInput(BaseModel):
    scene_ids: list[str] = Field(min_length=1, max_length=5)


def build_satellite_catalog_tools(context: SatelliteToolContext) -> list[BaseTool]:
    client = SatelliteGatewayClient(
        target=context.gateway_target,
        project_id=context.gateway_project_id,
        user_id=str(context.uid),
        run_id=context.run_id,
        token=sys_config.satellite_gateway_token.get_secret_value(),
        timeout_seconds=context.gateway_timeout_seconds,
    )

    async def list_satellite_sources() -> dict[str, Any]:
        return await _safe_call(client.list_sources())

    async def search_satellite_scenes(
        bbox: list[float],
        acquired_from: str,
        acquired_to: str,
        source_ids: list[str],
        collection_ids: list[str],
        satellites: list[str],
        sensors: list[str],
        processing_levels: list[str],
        max_cloud_cover: float | None,
        limit: int,
    ) -> dict[str, Any]:
        return await _safe_call(
            client.search_scenes(
                bbox=bbox,
                acquired_from=acquired_from,
                acquired_to=acquired_to,
                source_ids=source_ids,
                collection_ids=collection_ids,
                satellites=satellites,
                sensors=sensors,
                processing_levels=processing_levels,
                max_cloud_cover=max_cloud_cover,
                limit=limit,
            )
        )

    async def inspect_satellite_scenes(scene_ids: list[str]) -> dict[str, Any]:
        results = await asyncio.gather(
            *(client.get_scene(scene_id) for scene_id in scene_ids),
            return_exceptions=True,
        )
        scenes: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for scene_id, result in zip(scene_ids, results, strict=True):
            if isinstance(result, SatelliteGatewayError):
                errors.append({"scene_id": scene_id, "code": result.code})
            elif isinstance(result, Exception):
                errors.append({"scene_id": scene_id, "code": "gateway_error"})
            else:
                scenes.append(_bounded_scene(result))
        return {"scenes": scenes, "errors": errors}

    return [
        StructuredTool.from_function(
            name="list_satellite_sources",
            coroutine=list_satellite_sources,
            description="List satellite catalog sources available to the current project.",
        ),
        StructuredTool.from_function(
            name="search_satellite_scenes",
            coroutine=search_satellite_scenes,
            args_schema=SceneSearchInput,
            infer_schema=False,
            description="Search satellite scenes within an explicit WGS84 bbox and time range.",
        ),
        StructuredTool.from_function(
            name="inspect_satellite_scenes",
            coroutine=inspect_satellite_scenes,
            args_schema=SceneInspectInput,
            infer_schema=False,
            description="Inspect up to five candidate scenes and their bounded asset references.",
        ),
    ]


async def _safe_call(call) -> dict[str, Any]:
    try:
        return await call
    except SatelliteGatewayError as exc:
        return {"error": {"code": exc.code, "message": str(exc)}}


def _bounded_scene(scene: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        raw_metadata = json.loads(scene.get("metadata_json") or "{}")
        metadata = {
            key: raw_metadata[key]
            for key in ("tile_id", "orbit", "platform", "processing_baseline")
            if key in raw_metadata
        }
    except (TypeError, ValueError):
        pass
    return {
        "scene": scene.get("scene", {}),
        "footprint_wkt": scene.get("footprint_wkt", ""),
        "assets": scene.get("assets", [])[:20],
        "metadata": metadata,
    }
