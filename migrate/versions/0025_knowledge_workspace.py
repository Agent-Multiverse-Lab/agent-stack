"""知识库设置、目录与持久任务。"""

import sqlalchemy as sa
from alembic import op

revision = '0025_knowledge_workspace'
down_revision = '0024_run_created_by'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('knowledge_base', sa.Column('settings', sa.JSON(), nullable=False, server_default='{}'))
    # API/Worker 启动时 create_all 可能已创建新表及索引，但不会给已有表补列。
    op.create_table('knowledge_folder',
        sa.Column('folder_id', sa.String(64), primary_key=True),
        sa.Column('kb_id', sa.String(128), sa.ForeignKey('knowledge_base.kb_id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_id', sa.String(64), sa.ForeignKey('knowledge_folder.folder_id', ondelete='CASCADE')),
        sa.Column('name', sa.String(255), nullable=False),
        if_not_exists=True)
    op.create_index('ix_knowledge_folder_kb_id', 'knowledge_folder', ['kb_id'], if_not_exists=True)
    op.add_column('knowledge_file', sa.Column('folder_id', sa.String(64), sa.ForeignKey('knowledge_folder.folder_id', ondelete='SET NULL')))
    op.create_index('ix_knowledge_file_folder_id', 'knowledge_file', ['folder_id'])
    op.create_table('knowledge_task',
        sa.Column('task_id', sa.String(64), primary_key=True),
        sa.Column('kb_id', sa.String(128), sa.ForeignKey('knowledge_base.kb_id', ondelete='CASCADE'), nullable=False),
        sa.Column('uid', sa.String(128), sa.ForeignKey('user.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('operation', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('results', sa.JSON(), nullable=False),
        sa.Column('report', sa.JSON()), sa.Column('error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        if_not_exists=True)
    op.create_index('ix_knowledge_task_kb_id', 'knowledge_task', ['kb_id'], if_not_exists=True)
    op.create_index('ix_knowledge_task_uid', 'knowledge_task', ['uid'], if_not_exists=True)


def downgrade():
    op.drop_table('knowledge_task')
    op.drop_column('knowledge_file', 'folder_id')
    op.drop_table('knowledge_folder')
    op.drop_column('knowledge_base', 'settings')
