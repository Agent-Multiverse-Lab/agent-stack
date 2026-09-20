# Implementation Plan: 卫星数据资源库

计划版本：v0.1.0

## 1. Scope

实现 DP-SAT-001 至 DP-SAT-008 的最小资源库链路：Alembic/PostGIS 保存卫星业务数据，Go `gateway/`
提供 gRPC 查询，现有 `SatelliteAgent` 通过 Python 客户端使用目录结果并继续编排 MCP 处理工具。
当前四表 schema、固定 Sentinel/Landsat fixture、Gateway 与 Agent 调用代码已存在。本次建库工作的重点是
核对目标环境的迁移状态，并按 [STAC 1.1.0](https://www.ogc.org/standards/stac/) 的资源组织方式
接收真实多来源元数据。目标是标准对齐的内部目录；本计划不声称现有 gRPC 接口已经是 STAC API。

命名约定：产品和方案称“卫星数据资源库”；其中的 STAC 元数据组织与检索层称 `catalog`，
影像文件由 RustFS 保存，Go `gateway` 提供有界查询。既有 `satellite_catalog` proto、迁移版本、
生成文件和内部包名仍表示这一检索层，不作为产品名称；本次建库不修改这些公开或持久化标识。

## 2. Implementation order

1. 按 [catalog-data.md](implementation/catalog-data.md) 核对现有 schema、固定 fixture 和目标环境迁移状态，
   确定真实数据的来源、项目范围、对象存储位置和字段映射；增加 Asset key 的 Alembic 正向迁移。
2. 按 [catalog-data.md](implementation/catalog-data.md) 增加 STAC Collection/Item 清单的显式导入命令；
   先校验，再按 source → collection → scene → asset 顺序在事务内幂等写入。
   保留现有 fixture loader 供测试使用。
3. 按 [gateway-runtime.md](implementation/gateway-runtime.md) 为 `GetScene` 的 Asset 增加 key 字段并
   重新生成 Go/Python protobuf 代码，验证 Go gRPC 查询、项目隔离与分页。该字段是公开 gRPC
   契约变更，实施前需审阅影响；保留已有字段编号与语义。
4. 按 [agent-runtime.md](implementation/agent-runtime.md) 验证 SatelliteAgent 使用目录结果时保留来源、
   质量码、时相和资产引用，再将明确的资产交给已配置的 MCP 处理工具。
5. 完成静态、Go/Python 契约、目标环境迁移、导入及真实 gRPC 查询验证后更新部署说明。

## 3. Shared constraints

- Alembic 是唯一 schema owner；Go 启动时只连接和查询，不执行 DDL。
- PostgreSQL/PostGIS 保存目录真相，RustFS 保存影像对象；`object_ref` 不包含永久凭据。
- Gateway 只负责数据服务，不复制 MCP 的影像算法和处理状态机。
- bbox、时间、分页和项目范围在 Gateway 服务端再次校验。
- 生成代码来自唯一 proto，不手工维护第二套协议模型。
- `migrate/versions/0011_satellite_catalog.py` 已存在，不修改历史迁移；新增版本为资产加
  `asset_key`，把唯一约束从 `(scene_id, asset_role, band)` 调整为 `(scene_id, asset_key)`。
  已有数据的 key 从已知 band/role 映射，冲突或无法确定的记录先报告并处理，不能静默覆盖。
- Sentinel、Landsat 及后续来源共用四张表；`source_id` 标识来源，`collection_id` 标识产品系列，
  `scene_id` 与 `asset_id` 标识场景和对象，不以文件名或 checksum 当作全局主键。
- 导入命令只接受有明确项目归属和来源的本地 STAC 清单；不自动扫描全盘或在导入时调用未知公网目录。
  原始影像留在 RustFS，数据库只保存可追溯对象引用、大小、校验和、质量与空间元数据。
- 光学数据的云量可以填写；无云量概念的雷达数据保留 `NULL`，使用集合中的传感器和处理级别区分。
  不为每个卫星、传感器或资产类型新增独立表。
- [STAC Core 1.1.0](https://github.com/radiantearth/stac-spec) 作为元数据输入基线；按需接收
  [EO](https://github.com/stac-extensions/eo)、[SAR](https://github.com/stac-extensions/sar)、
  [Projection](https://github.com/stac-extensions/projection) 和
  [Raster](https://github.com/stac-extensions/raster) 扩展字段，不把某个扩展设为所有来源的必填项。
- STAC Catalog 用作项目/来源导航概念；Collection 对应产品系列，Item 对应场景，Asset 对应原始影像、
  波段、质量掩膜或预览。当前仅提供 gRPC 目录服务；STAC API 的 HTTP endpoints 是独立的公开契约变更。

## 4. Data flow example

`scripts/import_satellite_catalog.py` 的 `validate_stac` 和 `import_stac` 接收 STAC 1.1.0
Collection/Item JSON 与命令行指定的可信 `project_id`、外部 `source_key`。不同来源按同一核心字段映射，
允许的扩展字段进入有界 `metadata`；不以提供方的任意 JSON 覆盖系统字段。

```json
{
  "stac_version": "1.1.0",
  "stac_extensions": ["https://stac-extensions.github.io/eo/v2.0.0/schema.json", "https://stac-extensions.github.io/projection/v2.0.0/schema.json"],
  "type": "Feature",
  "id": "s2-20260401-a",
  "collection": "s2-l2a",
  "geometry": {"type": "Polygon", "coordinates": [[[116.1,39.7],[116.7,39.7],[116.7,40.2],[116.1,40.2],[116.1,39.7]]]},
  "bbox": [116.1, 39.7, 116.7, 40.2],
  "properties": {"datetime": "2026-04-01T02:41:00Z", "eo:cloud_cover": 3.2, "platform": "sentinel-2b", "instruments": ["msi"], "proj:code": "EPSG:32650"},
  "assets": {"B04": {"href": "s3://satellite/sentinel-public/s2-20260401-a/B04.tif", "type": "image/tiff; application=geotiff", "roles": ["data"]}},
  "links": [{"rel": "collection", "href": "../collections/s2-l2a.json"}]
}
```

示例是映射示意，完整输入还需 STAC Schema 要求的字段、对应 Collection 与可解析的 Asset 元数据。
外部 `source_key` 与 `project_id` 由导入命令可信参数给出。Collection/Item 的原始 ID 保留在元数据中；
数据库 `source_id`、`collection_id`、`scene_id`、`asset_id` 分别以项目/来源、来源/Collection、
来源/Collection/Item/版本、scene/Asset key 的规范化组合生成 UUIDv5；原始 ID 另外保留在
固定列或元数据中。这样 ID 稳定且不超过现有列长度，导入时仍检查原始字段长度和唯一性。
`satellite`、`sensor`、`processing_level` 优先取经过校验的 Collection/Item 属性，缺失时由
可信导入映射提供；没有映射则拒绝导入。`crs` 取 `proj:code` 等明确的原始 CRS 信息，
缺失时写入明确的 `unknown` 值。处理版本由可验证的来源字段或导入映射提供，缺失时用
`unversioned` 标记，同 ID 的已有内容若不一致则报冲突，不覆盖。
`Item.collection` 关联 Collection，`properties.datetime` 映射 `acquired_at`，
GeoJSON `geometry` 转为 WGS84 `footprint`，`assets` 的 key 单独存为 `asset_key`，
并与场景 ID 组合成稳定 `asset_id`。
`href` 只允许明确配置的 RustFS 对象地址，经归一化后存为 `object_ref`；对外提供访问时另外授权生成
临时链接，不把临时签名 URL 持久化。
Collection 的描述、许可、provider、空间/时间 extent 保留标准字段；当前表无法一一对应的标准字段
存入受限 `metadata` 并在导入时校验。光学与 SAR 项分别保留 EO 或 SAR 属性；`eo:cloud_cover`
不适用于 SAR 时为 `NULL`。项目范围仍由服务端控制，不从 STAC 属性信任外部身份。
`migrate/versions/0011_satellite_catalog.py` 现有的 `Polygon` 和非跨日期变更线 bbox 约束是范围边界；
超出该范围的合法 STAC Item（如 MultiPolygon/跨日期变更线）在本轮明确拒绝并报告，不静默裁剪。
`gateway/internal/catalog/store.go` 的 `SearchScenes` 按项目、WGS84 bbox 和时间检索，
`GetScene` 再返回该场景的有界资产列表；不返回影像字节。

`scripts/import_satellite_catalog.py` 的 `validate_stac` 在相同四表上的来源差异示例：

| 来源样例 | 读取的 STAC 字段 | 写入的区别 |
| --- | --- | --- |
| Sentinel-2 光学 | `eo:cloud_cover`、`platform`、B04 Asset | 云量进入固定列，B04 成为波段资产 |
| Sentinel-1 SAR | `sar:polarizations`、`platform`、VV Asset | 云量为 `NULL`，极化保留在受限元数据中 |
| Landsat-9 光学 | `eo:cloud_cover`、`instruments`、SR_B4 Asset | 独立来源和 Collection，SR_B4 保留原波段标识 |

## 5. Failure handling

- 目标库未执行到 `0011_satellite_catalog`、PostGIS 不可用或项目范围不明确时停止导入。
- STAC JSON 不符合 Core 或声明的扩展 schema、bbox/时间/footprint 不合法、scene 与 collection/source
  不一致，或同一批次有冲突 ID 时，先报告错误，不写入部分记录。
- 对象引用缺失、对象不存在或 checksum 缺失时记录可追溯质量码并阻止其作为可处理资产；
  不伪造链接。对同一批清单重复导入只更新同一稳定 ID，不产生重复场景。
- RustFS 对象检查只读取对象元数据，不整幅读取大文件；只有存储端已有可信校验和时才记录，
  否则以缺失校验和质量码标记，不把大小或 ETag 误报成内容校验和。
- Gateway 仍强制项目、bbox、时间和数量边界；导入成功不等于 MCP 可处理该资产。

## 6. Validation

- `go test ./...`（`gateway/`）
- `python -m unittest -v test.test_satellite_gateway test.test_satellite_agent`
- `ruff check`、`python -m py_compile`、`git diff --check`
- 有 PostgreSQL/PostGIS 与 Docker 时执行 migration、fixture load 和真实 gRPC smoke test。
- 用 Sentinel-2 光学、Sentinel-1 SAR 与 Landsat 光学样例验证重复导入、跨来源同名、缺失对象、
  无云量场景及跨项目隔离；抽查四表行数、外键、GiST 索引和 `GetScene` 的资产引用。
- 使用固定版本 STAC 1.1.0 Core Schema 与实际声明的扩展 Schema 验证样例；对不支持的 geometry、
  不可信 href 和不能转换的扩展字段返回可定位错误。验收区分“内部 STAC 元数据可导入”和“提供 STAC API”。
- 上述真实库检查只在明确的目标数据库执行；当前计划阶段不执行迁移或写入生产数据。
