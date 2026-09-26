"""ORM mappings for the Alembic-owned satellite imagery catalog."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import UserDefinedType

from .base import Base


class PostGISPolygon(UserDefinedType):
    """"""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "geometry(Polygon,4326)"


class SatelliteSource(Base):
    __tablename__ = "satellite_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_satellite_sources_project_name"),
    )

    source_id = Column(String(64), primary_key=True)
    project_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    provider = Column(String(64), nullable=False)
    is_enabled = Column(Boolean, nullable=False, server_default=true())
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    collections = relationship("SatelliteCollection", back_populates="source")


class SatelliteCollection(Base):
    __tablename__ = "satellite_collections"
    __table_args__ = (
        UniqueConstraint("source_id", "name", name="uq_satellite_collections_source_name"),
        UniqueConstraint("collection_id", "source_id", name="uq_satellite_collections_id_source"),
    )

    collection_id = Column(String(96), primary_key=True)
    source_id = Column(String(64), ForeignKey("satellite_sources.source_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    satellite = Column(String(64), nullable=False)
    sensor = Column(String(64), nullable=False)
    processing_level = Column(String(32), nullable=False)
    license = Column(String(128), nullable=False, server_default="")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    source = relationship("SatelliteSource", back_populates="collections")
    scenes = relationship("SatelliteScene", back_populates="collection")


class SatelliteScene(Base):
    __tablename__ = "satellite_scenes"
    __table_args__ = (
        CheckConstraint("bbox_west >= -180 AND bbox_east <= 180 AND bbox_west < bbox_east", name="ck_satellite_scenes_bbox_lon"),
        CheckConstraint("bbox_south >= -90 AND bbox_north <= 90 AND bbox_south < bbox_north", name="ck_satellite_scenes_bbox_lat"),
        CheckConstraint("cloud_cover IS NULL OR (cloud_cover >= 0 AND cloud_cover <= 100)", name="ck_satellite_scenes_cloud_cover"),
        ForeignKeyConstraint(
            ["collection_id", "source_id"],
            ["satellite_collections.collection_id", "satellite_collections.source_id"],
            ondelete="RESTRICT",
            name="fk_satellite_scenes_collection_source",
        ),
        UniqueConstraint("source_id", "provider_scene_id", "version", name="uq_satellite_scenes_provider_version"),
        Index("ix_satellite_scenes_acquired_at", "acquired_at"),
        Index("ix_satellite_scenes_collection_time", "collection_id", "acquired_at"),
        Index("ix_satellite_scenes_source", "source_id"),
        Index("ix_satellite_scenes_footprint", "footprint", postgresql_using="gist"),
    )

    scene_id = Column(String(128), primary_key=True)
    source_id = Column(String(64), nullable=False)
    collection_id = Column(String(96), nullable=False)
    provider_scene_id = Column(String(255), nullable=False)
    acquired_at = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    footprint = Column(PostGISPolygon(), nullable=False)
    bbox_west = Column(Float, nullable=False)
    bbox_south = Column(Float, nullable=False)
    bbox_east = Column(Float, nullable=False)
    bbox_north = Column(Float, nullable=False)
    cloud_cover = Column(Float)
    crs = Column(String(64), nullable=False)
    ground_sample_distance = Column(Float)
    version = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, server_default="available")
    quality = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    collection = relationship("SatelliteCollection", back_populates="scenes")
    assets = relationship("SatelliteSceneAsset", back_populates="scene")
    business_links = relationship("SatelliteBusinessScene", back_populates="scene")


class SatelliteSceneAsset(Base):
    __tablename__ = "satellite_scene_assets"
    __table_args__ = (
        UniqueConstraint("scene_id", "asset_key", name="uq_satellite_scene_assets_scene_asset_key"),
        Index("ix_satellite_scene_assets_scene", "scene_id"),
    )

    asset_id = Column(String(160), primary_key=True)
    scene_id = Column(String(128), ForeignKey("satellite_scenes.scene_id", ondelete="CASCADE"), nullable=False)
    asset_key = Column(String(255), nullable=False)
    asset_role = Column(String(32), nullable=False)
    band = Column(String(32), nullable=False, server_default="")
    object_ref = Column(String(1024))
    content_type = Column(String(128))
    checksum = Column(String(128))
    size_bytes = Column(BigInteger)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    scene = relationship("SatelliteScene", back_populates="assets")


class SatelliteBusinessScene(Base):
    __tablename__ = "satellite_business_scenes"
    __table_args__ = (
        CheckConstraint(
            "business_code IN ('crop_yield', 'crop_disaster', 'building_change', 'solar_pv')",
            name="ck_satellite_business_scenes_code",
        ),
        CheckConstraint(
            "scene_role IN ('monitoring', 'pre_event', 'post_event', 'training_reference', 'screening')",
            name="ck_satellite_business_scenes_role",
        ),
        Index("ix_satellite_business_scenes_code", "business_code"),
    )

    scene_id = Column(String(128), ForeignKey("satellite_scenes.scene_id", ondelete="CASCADE"), primary_key=True)
    business_code = Column(String(64), primary_key=True)
    scene_role = Column(String(32), nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    scene = relationship("SatelliteScene", back_populates="business_links")
