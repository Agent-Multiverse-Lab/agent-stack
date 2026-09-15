# Catalog Data Slice

关联需求：DP-SAT-001、DP-SAT-002、DP-SAT-003、DP-SAT-006  
关联任务：SAT-001、SAT-004

- `migrate/versions/0011_satellite_catalog.py` 创建 source、collection、scene 和 scene asset。
- scene 使用 PostGIS `geometry(Polygon, 4326)` 和 GiST 索引；同时保存 bbox 数值用于稳定契约输出。
- `scripts/generate_satellite_catalog_fixture.py` 生成确定性 JSON。
- `scripts/load_satellite_catalog_fixture.py` 仅作为显式维护命令加载已迁移数据库，不在 import 或服务启动时写库。
- `test/fixtures/satellite_catalog/manifest.json` 声明稳定 bad-case ID 与预期证据。
