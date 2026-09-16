"""以 STAC Asset key 区分同一场景的资产。"""

import sqlalchemy as sa
from alembic import op

revision = "0012_satellite_asset_key"
down_revision = "0011_satellite_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "satellite_scene_assets",
        sa.Column("asset_key", sa.String(255), nullable=True),
    )
    op.execute(
        """
        UPDATE satellite_scene_assets
        SET asset_key = COALESCE(
            NULLIF(metadata ->> 'asset_key', ''),
            NULLIF(band, ''),
            NULLIF(asset_role, '')
        )
        """
    )
    op.execute(
        """
        DO $$
        DECLARE conflict_scene text;
                conflict_key text;
        BEGIN
            IF EXISTS (SELECT 1 FROM satellite_scene_assets WHERE asset_key IS NULL) THEN
                RAISE EXCEPTION 'satellite asset_key backfill failed: empty legacy role/band';
            END IF;
            SELECT scene_id, asset_key INTO conflict_scene, conflict_key
            FROM satellite_scene_assets
            GROUP BY scene_id, asset_key
            HAVING count(*) > 1
            LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'satellite asset_key backfill conflict: scene %, key %',
                    conflict_scene, conflict_key;
            END IF;
        END $$
        """
    )
    op.alter_column("satellite_scene_assets", "asset_key", nullable=False)
    op.drop_constraint(
        "uq_satellite_scene_assets_role_band",
        "satellite_scene_assets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_satellite_scene_assets_scene_asset_key",
        "satellite_scene_assets",
        ["scene_id", "asset_key"],
    )


def downgrade() -> None:
    # 若新数据复用了 role/band，旧约束会拒绝降级，事务回滚且不会丢失资产。
    op.create_unique_constraint(
        "uq_satellite_scene_assets_role_band",
        "satellite_scene_assets",
        ["scene_id", "asset_role", "band"],
    )
    op.drop_constraint(
        "uq_satellite_scene_assets_scene_asset_key",
        "satellite_scene_assets",
        type_="unique",
    )
    op.drop_column("satellite_scene_assets", "asset_key")
