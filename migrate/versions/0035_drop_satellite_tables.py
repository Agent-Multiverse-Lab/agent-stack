"""清理废弃的卫星影像目录表与 PostGIS 扩展。"""

from alembic import op

revision = "0035_drop_satellite_tables"
down_revision = "0034_model_provider_column_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS satellite_business_scenes CASCADE")
    op.execute("DROP TABLE IF EXISTS satellite_scene_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS satellite_scenes CASCADE")
    op.execute("DROP TABLE IF EXISTS satellite_collections CASCADE")
    op.execute("DROP TABLE IF EXISTS satellite_sources CASCADE")
    op.execute("DROP EXTENSION IF EXISTS postgis_tiger_geocoder CASCADE")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology CASCADE")
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")


def downgrade() -> None:
    pass
