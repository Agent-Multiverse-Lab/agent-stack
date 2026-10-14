"""模型供应商恢复为平台共享配置；冲突数据要求显式选择来源。"""

import json
from collections import defaultdict

import sqlalchemy as sa
from alembic import context, op

from src.database.credential_types import decrypt_credential

revision = "0015_model_provider_global"
down_revision = "0014_agent_is_subagent"
branch_labels = None
depends_on = None

_NAMING = {"pk": "pk_%(table_name)s"}


def _signature(row) -> str:
    """只在内存比较解密后的业务值，保留所选行原有密文。"""
    try:
        key = decrypt_credential(row["api_key"]) if row["api_key"] else ""
        headers = json.loads(decrypt_credential(row["extra_headers"])) if row["extra_headers"] else {}
        if not isinstance(headers, dict) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in headers.items()
        ):
            raise ValueError
        normalized_headers = {name.lower(): value for name, value in headers.items()}
        if len(normalized_headers) != len(headers):
            raise ValueError
        models = []
        if not isinstance(row["enabled_models"], list):
            raise ValueError
        for model in row["enabled_models"]:
            if (
                not isinstance(model, dict)
                or set(model) - {"model_id", "model_type", "body_overrides", "capabilities"}
                or not isinstance(model.get("model_id"), str)
                or not model["model_id"]
                or not isinstance(model.get("model_type"), str)
                or not isinstance(model.get("body_overrides", {}), dict)
                or not isinstance(model.get("capabilities", []), list)
                or any(not isinstance(item, str) for item in model.get("capabilities", []))
            ):
                raise ValueError
            models.append({
                "model_id": model["model_id"],
                "model_type": model["model_type"],
                "body_overrides": model.get("body_overrides", {}),
                "capabilities": sorted(model.get("capabilities", [])),
            })
        if len({model["model_id"] for model in models}) != len(models):
            raise ValueError
        return json.dumps({
            "name": row["name"].strip(),
            "base_url": row["base_url"].rstrip("/"),
            "protocol": row["protocol"],
            "api_key": key,
            "extra_headers": normalized_headers,
            "is_enabled": row["is_enabled"],
            "enabled_models": sorted(models, key=lambda model: model["model_id"]),
        }, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError):
        raise RuntimeError("模型配置无法解密或规范化，原数据未修改") from None


def upgrade() -> None:
    connection = op.get_bind()
    table = sa.Table("model_provider", sa.MetaData(), autoload_with=connection)
    groups = defaultdict(list)
    for row in connection.execute(
        sa.select(table).order_by(table.c.provider_id, table.c.user_id)
    ).mappings():
        groups[row["provider_id"]].append((row, _signature(row)))
    conflicts = {
        provider_id for provider_id, rows in groups.items()
        if len({signature for _, signature in rows}) > 1
    }
    raw = context.get_x_argument(as_dictionary=True).get("model_provider_global_sources")
    try:
        sources = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        raise RuntimeError("全局模型配置来源映射无效，原数据未修改") from None
    if (
        not isinstance(sources, dict)
        or set(sources) != conflicts
        or any(type(value) is not int or value <= 0 for value in sources.values())
    ):
        raise RuntimeError(
            "冲突模型配置要求完整来源映射；请通过 -x model_provider_global_sources 指定，原数据未修改"
        )
    users = set(connection.execute(sa.text('SELECT id FROM "user"')).scalars())
    if not set(sources.values()) <= users:
        raise RuntimeError("模型配置来源用户不存在，原数据未修改")
    keep = {}
    for provider_id, rows in groups.items():
        source = sources.get(provider_id, rows[0][0]["user_id"])
        if not any(row["user_id"] == source for row, _ in rows):
            raise RuntimeError("模型配置来源记录不存在，原数据未修改")
        keep[provider_id] = source

    # 全部记录、凭据和映射验证成功后才修改数据及 schema。
    inspector = sa.inspect(connection)
    primary_key = inspector.get_pk_constraint("model_provider")["name"] or "pk_model_provider"
    foreign_keys = [
        item["name"] for item in inspector.get_foreign_keys("model_provider")
        if item["constrained_columns"] == ["user_id"]
    ]
    for provider_id, source in keep.items():
        connection.execute(table.delete().where(
            table.c.provider_id == provider_id, table.c.user_id != source,
        ))
    with op.batch_alter_table("model_provider", naming_convention=_NAMING) as batch:
        for name in foreign_keys:
            batch.drop_constraint(name, type_="foreignkey")
        batch.drop_constraint(primary_key, type_="primary")
        batch.drop_column("user_id")
        batch.create_primary_key("pk_model_provider", ["provider_id"])
        batch.alter_column("is_enabled", existing_type=sa.Boolean(), server_default=sa.false())


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(sa.text("SELECT COUNT(*) FROM model_provider")).scalar_one()
    owner = None
    if count:
        raw = context.get_x_argument(as_dictionary=True).get("model_provider_global_owner")
        try:
            owner = int(raw) if isinstance(raw, str) and raw.isdecimal() else None
        except ValueError:
            owner = None
        if owner is None or owner <= 0:
            raise RuntimeError("降级要求通过 -x model_provider_global_owner 指定接收用户，原数据未修改")
        if connection.execute(sa.text('SELECT id FROM "user" WHERE id=:id'), {"id": owner}).first() is None:
            raise RuntimeError("接收模型配置的用户不存在，原数据未修改")
    primary_key = sa.inspect(connection).get_pk_constraint("model_provider")["name"] or "pk_model_provider"
    op.add_column("model_provider", sa.Column("user_id", sa.Integer(), nullable=True))
    if count:
        connection.execute(sa.text("UPDATE model_provider SET user_id=:id"), {"id": owner})
    with op.batch_alter_table("model_provider", naming_convention=_NAMING) as batch:
        batch.drop_constraint(primary_key, type_="primary")
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.create_primary_key("pk_model_provider", ["user_id", "provider_id"])
        batch.create_foreign_key("fk_model_provider_user_id", "user", ["user_id"], ["id"], ondelete="CASCADE")
        batch.alter_column("is_enabled", existing_type=sa.Boolean(), server_default=None)
