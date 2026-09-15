"""Load the checked-in satellite catalog fixture into a migrated PostgreSQL database."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import asyncpg

from src.configs import config


def _postgres_url(value: str) -> str:
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _read(root: Path, name: str) -> list[dict[str, Any]]:
    return json.loads((root / f"{name}.json").read_text("utf-8"))


async def load_fixture(database_url: str, root: Path) -> None:
    connection = await asyncpg.connect(_postgres_url(database_url))
    try:
        async with connection.transaction():
            for source in _read(root, "sources"):
                await connection.execute(
                    """
                    INSERT INTO satellite_sources
                        (source_id, project_id, name, provider, metadata)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    ON CONFLICT (source_id) DO UPDATE SET
                        project_id = EXCLUDED.project_id,
                        name = EXCLUDED.name,
                        provider = EXCLUDED.provider,
                        metadata = EXCLUDED.metadata
                    """,
                    source["source_id"], source["project_id"], source["name"],
                    source["provider"], json.dumps(source["metadata"]),
                )
            for collection in _read(root, "collections"):
                await connection.execute(
                    """
                    INSERT INTO satellite_collections
                        (collection_id, source_id, name, satellite,
                         sensor, processing_level, license, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                    ON CONFLICT (collection_id) DO UPDATE SET
                        source_id = EXCLUDED.source_id,
                        name = EXCLUDED.name,
                        satellite = EXCLUDED.satellite,
                        sensor = EXCLUDED.sensor,
                        processing_level = EXCLUDED.processing_level,
                        license = EXCLUDED.license,
                        metadata = EXCLUDED.metadata
                    """,
                    collection["collection_id"], collection["source_id"],
                    collection["name"], collection["satellite"], collection["sensor"],
                    collection["processing_level"], collection["license"],
                    json.dumps(collection["metadata"]),
                )
            for scene in _read(root, "scenes"):
                west, south, east, north = scene["bbox"]
                await connection.execute(
                    """
                    INSERT INTO satellite_scenes
                        (scene_id, source_id, collection_id, provider_scene_id,
                         acquired_at, footprint,
                         bbox_west, bbox_south, bbox_east, bbox_north,
                         cloud_cover, crs, ground_sample_distance, version,
                         status, quality, metadata)
                    VALUES ($1, $2, $3, $4, $5::timestamptz,
                            ST_GeomFromText($6, 4326), $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16::jsonb, $17::jsonb)
                    ON CONFLICT (scene_id) DO UPDATE SET
                        acquired_at = EXCLUDED.acquired_at,
                        footprint = EXCLUDED.footprint,
                        cloud_cover = EXCLUDED.cloud_cover,
                        version = EXCLUDED.version,
                        status = EXCLUDED.status,
                        quality = EXCLUDED.quality,
                        metadata = EXCLUDED.metadata
                    """,
                    scene["scene_id"], scene["source_id"], scene["collection_id"],
                    scene["provider_scene_id"],
                    scene["acquired_at"], scene["footprint_wkt"],
                    west, south, east, north, scene["cloud_cover"], scene["crs"],
                    scene["ground_sample_distance"], scene["version"],
                    scene["status"], json.dumps(scene["quality"]),
                    json.dumps(scene["metadata"]),
                )
            for asset in _read(root, "assets"):
                await connection.execute(
                    """
                    INSERT INTO satellite_scene_assets
                        (asset_id, scene_id, asset_role, band, object_ref,
                         content_type, checksum, size_bytes, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                    ON CONFLICT (asset_id) DO UPDATE SET
                        object_ref = EXCLUDED.object_ref,
                        content_type = EXCLUDED.content_type,
                        checksum = EXCLUDED.checksum,
                        size_bytes = EXCLUDED.size_bytes,
                        metadata = EXCLUDED.metadata
                    """,
                    asset["asset_id"], asset["scene_id"], asset["asset_role"],
                    asset["band"], asset["object_ref"], asset["content_type"],
                    asset["checksum"], asset["size_bytes"],
                    json.dumps(asset["metadata"]),
                )
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=config.database_url,
        help="PostgreSQL URL; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path("test/fixtures/satellite_catalog"),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    asyncio.run(load_fixture(args.database_url, args.fixture_root))


if __name__ == "__main__":
    main()
