from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import grpc
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from . import satellite_catalog_pb2 as pb
from . import satellite_catalog_pb2_grpc as pb_grpc

_Response = TypeVar("_Response", bound=Message)


class SatelliteGatewayError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SatelliteGatewayClient:
    """Small async boundary around the generated satellite catalog stub."""

    def __init__(
        self,
        *,
        target: str,
        project_id: str,
        user_id: str,
        run_id: str,
        token: str,
        timeout_seconds: float,
    ) -> None:
        self.target = target
        self.project_id = project_id
        self.user_id = user_id
        self.run_id = run_id
        self.token = token
        self.timeout_seconds = timeout_seconds

    async def list_sources(self) -> dict[str, Any]:
        return await self._invoke(
            lambda stub: stub.ListSources(pb.ListSourcesRequest())
        )

    async def search_scenes(
        self,
        *,
        bbox: list[float],
        acquired_from: str,
        acquired_to: str,
        source_ids: list[str] | None = None,
        collection_ids: list[str] | None = None,
        satellites: list[str] | None = None,
        sensors: list[str] | None = None,
        processing_levels: list[str] | None = None,
        max_cloud_cover: float | None = None,
        limit: int = 20,
        page_token: str = "",
    ) -> dict[str, Any]:
        if len(bbox) != 4:
            raise SatelliteGatewayError("invalid_request", "bbox 必须包含 west, south, east, north")
        request = pb.SearchScenesRequest(
            bbox=pb.BoundingBox(
                west=bbox[0], south=bbox[1], east=bbox[2], north=bbox[3]
            ),
            acquired_from=acquired_from,
            acquired_to=acquired_to,
            source_ids=source_ids or [],
            collection_ids=collection_ids or [],
            satellites=satellites or [],
            sensors=sensors or [],
            processing_levels=processing_levels or [],
            limit=limit,
            page_token=page_token,
        )
        if max_cloud_cover is not None:
            request.max_cloud_cover = max_cloud_cover
        return await self._invoke(lambda stub: stub.SearchScenes(request))

    async def get_scene(self, scene_id: str) -> dict[str, Any]:
        return await self._invoke(
            lambda stub: stub.GetScene(pb.GetSceneRequest(scene_id=scene_id))
        )

    async def _invoke(
        self,
        call: Callable[[pb_grpc.SatelliteCatalogServiceStub], Awaitable[_Response]],
    ) -> dict[str, Any]:
        metadata = (
            ("authorization", f"Bearer {self.token}"),
            ("x-project-id", self.project_id),
            ("x-user-id", self.user_id),
            ("x-run-id", self.run_id),
        )
        try:
            async with grpc.aio.insecure_channel(self.target) as channel:
                stub = pb_grpc.SatelliteCatalogServiceStub(channel)
                response = await call(_MetadataStub(stub, metadata, self.timeout_seconds))
        except grpc.aio.AioRpcError as exc:
            raise SatelliteGatewayError(
                exc.code().name.lower(), exc.details() or "satellite gateway request failed"
            ) from exc
        return MessageToDict(
            response,
            preserving_proto_field_name=True,
            always_print_fields_with_no_presence=True,
        )


class _MetadataStub:
    """Attach trusted call metadata without leaking it into model arguments."""

    def __init__(
        self,
        stub: pb_grpc.SatelliteCatalogServiceStub,
        metadata: tuple[tuple[str, str], ...],
        timeout: float,
    ) -> None:
        self._stub = stub
        self._metadata = metadata
        self._timeout = timeout

    def ListSources(self, request: Message):
        return self._stub.ListSources(
            request, metadata=self._metadata, timeout=self._timeout
        )

    def SearchScenes(self, request: Message):
        return self._stub.SearchScenes(
            request, metadata=self._metadata, timeout=self._timeout
        )

    def GetScene(self, request: Message):
        return self._stub.GetScene(
            request, metadata=self._metadata, timeout=self._timeout
        )
