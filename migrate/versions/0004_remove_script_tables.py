"""删除旧剧本与风格资产表。"""

from alembic import op

revision = "0004_remove_script_tables"
down_revision = "0003_attachment_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """删除不再属于当前业务的旧表。"""
    for table_name in (
        "style_portfolio",
        "script_line",
        "script_scene",
        "storyboard_frame",
        "episode_outline",
        "episode_script",
        "character",
        "episode",
        "script_project",
    ):
        op.drop_table(table_name, if_exists=True)


def downgrade() -> None:
    """旧业务表及其数据不支持恢复。"""
    raise RuntimeError("旧剧本表删除迁移不可回退")
