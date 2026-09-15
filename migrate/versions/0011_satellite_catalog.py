"""增加卫星影像多源目录。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_satellite_catalog"
down_revision = "0010_model_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "satellite_sources",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", name="uq_satellite_sources_project_name"),
    )

    op.create_table(
        "satellite_collections",
        sa.Column("collection_id", sa.String(96), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("satellite_sources.source_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("satellite", sa.String(64), nullable=False),
        sa.Column("sensor", sa.String(64), nullable=False),
        sa.Column("processing_level", sa.String(32), nullable=False),
        sa.Column("license", sa.String(128), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "name", name="uq_satellite_collections_source_name"),
        sa.UniqueConstraint("collection_id", "source_id", name="uq_satellite_collections_id_source"),
    )
    op.create_table(
        "satellite_scenes",
        sa.Column("scene_id", sa.String(128), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("collection_id", sa.String(96), nullable=False),
        sa.Column("provider_scene_id", sa.String(255), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("footprint", sa.Text(), nullable=False),
        sa.Column("bbox_west", sa.Float(), nullable=False),
        sa.Column("bbox_south", sa.Float(), nullable=False),
        sa.Column("bbox_east", sa.Float(), nullable=False),
        sa.Column("bbox_north", sa.Float(), nullable=False),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("crs", sa.String(64), nullable=False),
        sa.Column("ground_sample_distance", sa.Float(), nullable=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="available"),
        sa.Column("quality", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("bbox_west >= -180 AND bbox_east <= 180 AND bbox_west < bbox_east", name="ck_satellite_scenes_bbox_lon"),
        sa.CheckConstraint("bbox_south >= -90 AND bbox_north <= 90 AND bbox_south < bbox_north", name="ck_satellite_scenes_bbox_lat"),
        sa.CheckConstraint("cloud_cover IS NULL OR (cloud_cover >= 0 AND cloud_cover <= 100)", name="ck_satellite_scenes_cloud_cover"),
        sa.ForeignKeyConstraint(
            ["collection_id", "source_id"],
            ["satellite_collections.collection_id", "satellite_collections.source_id"],
            ondelete="RESTRICT",
            name="fk_satellite_scenes_collection_source",
        ),
        sa.UniqueConstraint("source_id", "provider_scene_id", "version", name="uq_satellite_scenes_provider_version"),
    )
    op.execute("ALTER TABLE satellite_scenes ALTER COLUMN footprint TYPE geometry(Polygon, 4326) USING ST_GeomFromText(footprint, 4326)")
    op.create_index("ix_satellite_scenes_acquired_at", "satellite_scenes", ["acquired_at"])
    op.create_index("ix_satellite_scenes_collection_time", "satellite_scenes", ["collection_id", "acquired_at"])
    op.create_index("ix_satellite_scenes_source", "satellite_scenes", ["source_id"])
    op.execute("CREATE INDEX ix_satellite_scenes_footprint ON satellite_scenes USING gist (footprint)")

    op.create_table(
        "satellite_scene_assets",
        sa.Column("asset_id", sa.String(160), primary_key=True),
        sa.Column("scene_id", sa.String(128), sa.ForeignKey("satellite_scenes.scene_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_role", sa.String(32), nullable=False),
        sa.Column("band", sa.String(32), nullable=False, server_default=""),
        sa.Column("object_ref", sa.String(1024), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scene_id", "asset_role", "band", name="uq_satellite_scene_assets_role_band"),
    )
    op.create_index("ix_satellite_scene_assets_scene", "satellite_scene_assets", ["scene_id"])


def downgrade() -> None:
    op.drop_table("satellite_scene_assets")
    op.execute("DROP INDEX IF EXISTS ix_satellite_scenes_footprint")
    op.drop_table("satellite_scenes")
    op.drop_table("satellite_collections")
    op.drop_table("satellite_sources")
