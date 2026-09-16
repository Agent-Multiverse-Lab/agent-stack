# Catalog Data Slice

关联需求：DP-SAT-001、DP-SAT-002、DP-SAT-003、DP-SAT-006、DP-SAT-007、DP-SAT-008
关联任务：SAT-001、SAT-004、SAT-006

- `migrate/versions/0011_satellite_catalog.py` 创建 source、collection、scene 和 scene asset。
- 新 Alembic 迁移在 `satellite_scene_assets` 加非空 `asset_key`，检查现有数据后重建
  `(scene_id, asset_key)` 唯一约束；不修改已经存在的 0011 迁移文件。
- scene 使用 PostGIS `geometry(Polygon, 4326)` 和 GiST 索引；同时保存 bbox 数值用于稳定契约输出。
- `scripts/generate_satellite_catalog_fixture.py` 生成确定性 JSON。
- `scripts/load_satellite_catalog_fixture.py` 仅作为显式维护命令加载已迁移数据库，不在 import 或服务启动时写库。
- `test/fixtures/satellite_catalog/manifest.json` 声明稳定 bad-case ID 与预期证据。
- `scripts/import_satellite_catalog.py` 接收显式指定的 STAC 1.1.0 Collection/Item JSON、外部
  `source_key` 和可信项目 ID，
  先验证 Schema、来源/集合/场景/资产关系，再用事务与稳定 ID 幂等写入现有四表；
  不改造固定 fixture loader 为生产导入器。
- 导入验证覆盖 UTC 时间、WGS84 bbox/footprint、原始 CRS、云量可空、质量码、MinIO 对象引用、
  checksum 和大小。缺失或不一致的资产按根计划记录质量状态，不当作可处理资产。
- EO、SAR、Projection、Raster 扩展只校验输入实际声明的版本；在 `metadata` 保存允许的标准字段，
  不新增按卫星划分的表，也不把内外部对象 URI 或密钥混写。
- `validate_stac` 检查 STAC Core、Collection/Item 关联、单次观测时间、WGS84 Polygon/bbox、ID 长度，
  映射到现有 schema；超出 `geometry(Polygon, 4326)` 或经度边界的合法 STAC Item 明确失败。
- MinIO 对象元数据检查只确认对象存在、大小及已有的可信校验和；不为入库把大幅影像整幅读入。
  不完整资产保留可追溯质量码，不能作为可处理输入。
- 若目标库已有不同项目占用相同 ID，导入失败，不通过 upsert 改写原项目归属；
  测试同一清单重复运行、跨来源相同文件名以及源/集合关联冲突。
