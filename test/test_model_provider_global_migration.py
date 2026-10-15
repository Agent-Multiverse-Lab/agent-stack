"""从个人配置收敛为全局配置时的预检、冲突选择与安全降级。"""

import json
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from src.configs import config
from src.database.credential_types import encrypt_credential
from src.database.models import ModelProvider, User
from test.test_model_provider_global import migration


class ModelProviderGlobalMigrationTest(unittest.TestCase):
    def setUp(self):
        cipher = patch.object(config, "model_credential_key", SecretStr(Fernet.generate_key().decode()))
        cipher.start()
        self.addCleanup(cipher.stop)
        self.engine = create_engine("sqlite://")
        self.db = self.engine.connect()
        self.transaction = self.db.begin()
        User.__table__.create(self.db)
        self.db.execute(User.__table__.insert(), [
            {"id": i, "uid": f"u{i}", "email": f"u{i}@test", "password_hash": "unused"}
            for i in (1, 2, 3)
        ])
        self.operations = Operations(MigrationContext.configure(self.db))
        initial = migration("0008_model_provider.py")
        scoped = migration("0009_model_provider_user.py")
        with patch.object(initial, "op", self.operations):
            initial.upgrade()
        with patch.object(scoped, "op", self.operations), patch.object(scoped.context, "get_x_argument", return_value={}):
            scoped.upgrade()
        self.migration = migration("0015_model_provider_global.py")

    def tearDown(self):
        self.transaction.rollback()
        self.db.close()
        self.engine.dispose()

    def table(self):
        return Table("model_provider", MetaData(), autoload_with=self.db)

    def insert(self, user_id, **changes):
        values = {
            "user_id": user_id, "provider_id": "deepseek", "name": "DeepSeek",
            "base_url": "https://example.com/v1", "protocol": "openai_compatible",
            "api_key": encrypt_credential("shared-key"),
            "extra_headers": encrypt_credential(json.dumps({"X-Private": "shared-header"})),
            "is_enabled": True,
            "enabled_models": [{"model_id": "chat", "model_type": "deepseek", "capabilities": ["chat", "tools"]}],
            **changes,
        }
        self.db.execute(self.table().insert().values(**values))
        return values

    def run_migration(self, direction="upgrade", **arguments):
        with patch.object(self.migration, "op", self.operations), patch.object(
            self.migration.context, "get_x_argument", return_value=arguments,
        ):
            getattr(self.migration, direction)()

    def test_empty_upgrade_matches_global_schema_and_downgrade(self):
        self.run_migration()
        columns = {column["name"] for column in inspect(self.db).get_columns("model_provider")}
        self.assertEqual(columns, set(ModelProvider.__table__.columns.keys()))
        self.assertEqual(inspect(self.db).get_pk_constraint("model_provider")["constrained_columns"], ["provider_id"])
        self.assertEqual(inspect(self.db).get_foreign_keys("model_provider"), [])
        self.run_migration("downgrade")
        self.assertEqual(inspect(self.db).get_pk_constraint("model_provider")["constrained_columns"], ["user_id", "provider_id"])

    def test_semantically_identical_rows_merge_and_preserve_selected_ciphertext(self):
        original = self.insert(1)
        self.insert(2, base_url="https://example.com/v1/", enabled_models=[{
            "model_id": "chat", "model_type": "deepseek", "body_overrides": {}, "capabilities": ["tools", "chat"],
        }])
        self.run_migration()
        rows = list(self.db.execute(select(self.table())).mappings())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["api_key"], original["api_key"])
        self.assertEqual(rows[0]["extra_headers"], original["extra_headers"])

    def test_conflict_mapping_is_validated_before_any_mutation(self):
        self.insert(1)
        self.insert(2, name="Different")
        before = list(self.db.execute(select(self.table())).mappings())
        for raw in (None, "bad json", "[]", "{}", '{"deepseek":true}', '{"deepseek":9}', '{"deepseek":3}', '{"deepseek":2,"extra":1}'):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                self.run_migration(model_provider_global_sources=raw)
            self.assertEqual(list(self.db.execute(select(self.table())).mappings()), before)
            self.assertIn("user_id", self.table().columns)

    def test_explicit_source_preserves_config_and_downgrade_requires_owner(self):
        self.insert(1)
        selected = self.insert(2, name="Selected", api_key=encrypt_credential("selected-key"))
        self.run_migration(model_provider_global_sources='{"deepseek":2}')
        row = self.db.execute(select(self.table())).mappings().one()
        self.assertEqual(row["name"], "Selected")
        self.assertEqual(row["api_key"], selected["api_key"])
        for raw in (None, "bad", "0", "9"):
            with self.subTest(owner=raw), self.assertRaises(RuntimeError):
                self.run_migration("downgrade", model_provider_global_owner=raw)
            self.assertNotIn("user_id", self.table().columns)
        self.run_migration("downgrade", model_provider_global_owner="1")
        row = self.db.execute(select(self.table())).mappings().one()
        self.assertEqual(row["user_id"], 1)
        self.assertEqual(row["api_key"], selected["api_key"])

    def test_unreadable_credentials_stop_before_modifying_schema_or_rows(self):
        self.insert(1)
        with patch.object(config, "model_credential_key", SecretStr("")), self.assertRaises(RuntimeError):
            self.run_migration()
        self.assertIn("user_id", self.table().columns)
        self.assertEqual(self.db.execute(text("SELECT COUNT(*) FROM model_provider")).scalar_one(), 1)

    def test_single_record_needs_no_source_and_extra_mapping_is_rejected(self):
        original = self.insert(1)
        with self.assertRaises(RuntimeError):
            self.run_migration(model_provider_global_sources='{"deepseek":1}')
        self.run_migration()
        self.assertEqual(self.db.execute(select(self.table().c.api_key)).scalar_one(), original["api_key"])


class QwenProviderIdMigrationTest(unittest.TestCase):
    def setUp(self):
        cipher = patch.object(
            config,
            "model_credential_key",
            SecretStr(Fernet.generate_key().decode()),
        )
        cipher.start()
        self.addCleanup(cipher.stop)
        self.engine = create_engine("sqlite://")
        ModelProvider.__table__.create(self.engine)
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.operations = Operations(MigrationContext.configure(self.connection))
        self.migration = migration("0016_qwen_provider_id.py")

    def tearDown(self):
        self.transaction.rollback()
        self.connection.close()
        self.engine.dispose()

    def insert(self, provider_id: str):
        self.connection.execute(
            ModelProvider.__table__.insert().values(
                provider_id=provider_id,
                name="Qwen",
                base_url="https://example.com/v1",
                protocol="openai_compatible",
                api_key="secret",
                extra_headers={},
                is_enabled=True,
                enabled_models=[],
            )
        )

    def test_upgrade_and_downgrade_rename_without_changing_configuration(self):
        self.insert("qwen")
        with patch.object(self.migration, "op", self.operations):
            self.migration.upgrade()
        row = self.connection.execute(
            select(ModelProvider.__table__).where(
                ModelProvider.__table__.c.provider_id == "dashscope"
            )
        ).mappings().one()
        self.assertEqual(row["name"], "Qwen")
        with patch.object(self.migration, "op", self.operations):
            self.migration.downgrade()
        self.assertEqual(
            self.connection.execute(
                select(ModelProvider.__table__.c.provider_id)
            ).scalar_one(),
            "qwen",
        )

    def test_conflicting_ids_stop_before_mutation(self):
        self.insert("qwen")
        self.insert("dashscope")
        with patch.object(self.migration, "op", self.operations), self.assertRaises(
            RuntimeError
        ):
            self.migration.upgrade()
        self.assertEqual(
            set(
                self.connection.execute(
                    select(ModelProvider.__table__.c.provider_id)
                ).scalars()
            ),
            {"qwen", "dashscope"},
        )
