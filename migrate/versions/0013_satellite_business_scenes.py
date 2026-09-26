"""按业务场景组织影像，不复制场景或栅格资产。"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_satellite_business_scenes"
down_revision = "0012_satellite_asset_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "satellite_business_scenes",
        sa.Column("scene_id", sa.String(128), sa.ForeignKey("satellite_scenes.scene_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("business_code", sa.String(64), primary_key=True),
        sa.Column("scene_role", sa.String(32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "business_code IN ('crop_yield', 'crop_disaster', 'building_change', 'solar_pv')",
            name="ck_satellite_business_scenes_code",
        ),
        sa.CheckConstraint(
            "scene_role IN ('monitoring', 'pre_event', 'post_event', 'training_reference', 'screening')",
            name="ck_satellite_business_scenes_role",
        ),
    )
    op.create_index("ix_satellite_business_scenes_code", "satellite_business_scenes", ["business_code"])


def downgrade() -> None:
    op.drop_table("satellite_business_scenes")
