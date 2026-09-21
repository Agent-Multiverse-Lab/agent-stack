# OGC Control-plane Data Slice

关联需求：DP-OGC-001、DP-OGC-002、DP-OGC-003、DP-OGC-004
关联任务：OGC-001、OGC-004

- 新增 Alembic 迁移创建 `ogc_services`、`ogc_layers`、`ogc_layer_assets`、`ogc_themes`、
  `ogc_theme_layers`；不修改 `0011_satellite_catalog.py` 和 `0012_satellite_asset_key.py`。
- 所有根记录包含 `project_id`；数据库外键与 Gateway 事务共同保证 layer asset 同项目、theme layer 同 service。
- `ogc_services` 合并服务元数据与默认配置，避免拆成只有一对一关系的 metadata/config 表。
- 样式使用受限 JSONB schema 保存 band/rgba、nodata、resampling 等可验证配置；未知键和脚本字段被拒绝。
- 发布状态、版本、创建/更新时间和操作者形成最小审计信息；首期不建立通用审计事件或缓存任务表。
- 接入适配器测试覆盖秒/毫秒时间、未知时间哨兵、CRS 表达、bbox 顺序和参考文档拼写别名。

## Proposed columns

以下是首期迁移的字段基线；实现时可按仓库现有 UUID、时间戳和命名约定调整类型，但不得改变归属关系：

### `ogc_services`

| Column | Type | Contract |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `project_id` | UUID | 受信项目归属；与 `service_key` 唯一 |
| `service_key` | varchar | 稳定、URL-safe 业务标识 |
| `title` / `abstract` | text | 对外服务描述 |
| `keywords` | text[] | 可为空的检索词 |
| `contact` | jsonb | 受限联系信息 schema，不存凭据 |
| `default_render_config` | jsonb | 默认格式、背景色、重采样等受限配置 |
| `enabled` | boolean | 服务级开关，不代表 renderer 健康 |
| `version` | bigint | 乐观并发版本，从 1 开始 |
| `created_by` / `updated_by` | UUID | 受信操作者 |
| `created_at` / `updated_at` | timestamptz | UTC 审计时间 |

### `ogc_layers`

| Column | Type | Contract |
| --- | --- | --- |
| `id` / `project_id` / `service_id` | UUID | 主键、项目和所属 service |
| `layer_key` | varchar | service 内唯一稳定标识 |
| `title` / `abstract` | text | 图层描述 |
| `status` | varchar | `draft`、`published`、`disabled` |
| `style` | jsonb | 受限 band/rgba、nodata、resampling 配置 |
| `min_zoom` / `max_zoom` | smallint | `0 <= min_zoom <= max_zoom` |
| `version` | bigint | 条件更新版本 |
| `published_at` / `published_by` | timestamptz / UUID | 未发布时为 `NULL` |
| `created_by` / `updated_by` | UUID | 受信操作者 |
| `created_at` / `updated_at` | timestamptz | UTC 审计时间 |

### `ogc_layer_assets`

| Column | Type | Contract |
| --- | --- | --- |
| `layer_id` / `asset_id` | UUID | 联合主键；asset 引用 `satellite_scene_assets` |
| `project_id` | UUID | 用于数据库级同项目复合外键 |
| `priority` | integer | 重叠时顺序，数值小者优先 |
| `enabled` | boolean | 临时排除资产而不删除关系 |
| `created_at` | timestamptz | UTC 关联时间 |

### `ogc_themes`

| Column | Type | Contract |
| --- | --- | --- |
| `id` / `project_id` / `service_id` | UUID | 主键、项目和所属 service |
| `theme_key` | varchar | service 内唯一稳定标识 |
| `title` / `abstract` | text | 主题描述 |
| `status` | varchar | `draft`、`published`、`disabled` |
| `version` | bigint | 条件更新版本 |
| `published_at` / `published_by` | timestamptz / UUID | 未发布时为 `NULL` |
| `created_by` / `updated_by` | UUID | 受信操作者 |
| `created_at` / `updated_at` | timestamptz | UTC 审计时间 |

### `ogc_theme_layers`

| Column | Type | Contract |
| --- | --- | --- |
| `theme_id` / `layer_id` | UUID | 联合主键 |
| `project_id` / `service_id` | UUID | 用于数据库级同项目、同 service 复合外键 |
| `sort_order` | integer | 主题中的稳定显示顺序 |
| `visible` | boolean | 默认可见性 |
| `style_override` | jsonb | 可为空的受限覆盖，不执行脚本 |
| `created_at` | timestamptz | UTC 关联时间 |

`ogc_services`、`ogc_layers`、`ogc_themes` 分别增加支持复合外键的唯一键；删除 service、layer、theme 时默认
`RESTRICT`，由显式业务操作先解除关系。发布中的 layer/theme 不允许直接删除。
