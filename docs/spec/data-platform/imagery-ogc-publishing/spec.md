# 影像 OGC 发布能力规格

## 1. Context

本能力参考《系统调用接口文档 V1.0》中 `usmetas`、`usmaps` 和 Unispace OGC Raster Server
暴露的能力，但不照搬其接口字段或数据库结构。该文档作为能力清单：影像元数据登记与查询、图层和主题管理、
发布/取消发布、WMTS/WMS 服务以及缓存清理。平台内部仍以
[Satellite Imagery Catalog Spec](../satellite-imagery-catalog/spec.md) 的 STAC 风格目录为影像事实来源。

数据平台分为四层：

```text
SatelliteAgent
  -> read/mutation tools
     -> Go Gateway: catalog + publishing control plane
        -> PostgreSQL/PostGIS metadata
        -> RustFS object references

OGC renderer (later phase)
  -> published configuration
  -> RustFS raster reads
  -> WMTS/WMS + tile cache
```

### DP-OGC-001 Catalog remains the source of truth

影像接入继续写入 `satellite_sources`、`satellite_collections`、`satellite_scenes` 和
`satellite_scene_assets`。发布层只引用已验证、可处理的 scene asset，不复制 footprint、采集时间、波段元数据或
栅格字节。路径、URL 和文档中的 `dataurl` 只作为接入适配器输入，不作为跨系统身份。

### DP-OGC-002 Publishing control-plane data

控制面新增五类记录：

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `ogc_services` | 项目内服务身份、标题、摘要、联系信息和默认渲染配置 | `project_id + service_key` 唯一 |
| `ogc_layers` | 可独立发布的逻辑图层、样式、缩放范围和发布状态 | 隶属 service；`service_id + layer_key` 唯一 |
| `ogc_layer_assets` | 图层与 `satellite_scene_assets` 的有序多对多关系 | `layer_id + asset_id` 唯一；禁止跨项目引用 |
| `ogc_themes` | 将多个图层组织为可发布主题 | 隶属 service；`service_id + theme_key` 唯一 |
| `ogc_theme_layers` | 主题内图层顺序、可见性和可选覆盖样式 | `theme_id + layer_id` 唯一；禁止跨 service 引用 |

`ogc_layers.status` 和 `ogc_themes.status` 使用 `draft`、`published`、`disabled`。发布记录至少保存
`published_at`、`published_by` 和版本号，更新时使用乐观并发条件，避免旧配置覆盖新配置。缓存清理是明确的运行时操作，
首期不为其建立独立持久化表。

### DP-OGC-003 Data to collect

影像接入必须收集能够支撑检索、质量判断和渲染的数据；缺失项使用 `NULL` 与质量状态表达，不使用特殊哨兵时间。

| Group | Required data |
| --- | --- |
| 身份与隔离 | trusted `project_id`、source、collection、原始 scene/item ID、asset key、稳定内部 ID |
| 时空 | UTC `acquired_at`、WGS84 footprint/bbox、原始 CRS、可选归一化 EPSG/PROJ 表达 |
| 栅格 | width/height、band count、band name/role、data type、nodata、pixel resolution、affine transform |
| 存储与完整性 | RustFS object reference、media type、byte size、可信 checksum、对象存在性 |
| 质量与溯源 | processing level/version、producer、created/modified time、cloud cover（适用时）、quality code |
| 发布 | service/layer/theme key、标题、样式、band/rgba 映射、resampling、min/max zoom、发布状态与版本 |

建议收集但不阻止首期导入的数据包括像元统计、缩略图、许可、provider、太阳高度角、SAR 极化方式和轨道方向。
密钥、临时签名 URL、任意供应商私有 JSON 和栅格字节不得进入通用元数据字段。

### DP-OGC-004 Normalization of reference-document ambiguities

- 文档中秒和毫秒混用的时间统一解析为带时区 UTC 时间；未知时间哨兵值转换为 `NULL` 并记录质量码。
- `SPRID`、EPSG 和 PROJ 文本不得混为一个整数；保留原始 CRS 表达，并在可验证时保存归一化代码。
- bbox、corner 和 lat/lon rectangle 在接入边界显式转换为 WGS84 `[west, south, east, north]`。
- `mfsize`/`mfilesize`、`ditme` 等拼写差异只在适配器中兼容，内部字段保持单一命名。
- `text/plain` JSON、正则路径检索和 JMESPath 属于参考系统的传输/查询实现，不成为平台持久化契约。

### DP-OGC-005 Read and mutation contracts

首期只提供有界的结构化操作，不开放任意 SQL、正则扫描存储路径或用户提供的 JMESPath：

- Read: `list_sources`、`search_scenes`、`get_scene`、`list_layers`、`get_layer`、`list_themes`、
  `get_service_capabilities`。
- Mutation: `import_raster`、`update_scene_metadata`、`remove_scene`、`create_layer`、`update_layer`、
  `attach_scene_to_layer`、`create_theme`、`publish_layer`、`publish_theme`、`clear_tile_cache`。

所有调用由服务端注入 project/user/run 身份。读取工具使用边界、分页和项目隔离；修改工具要求 Human-in-the-loop
批准，并由 Gateway 再次校验身份、引用归属和状态迁移。`import_raster` 表示受控接入流程，不允许 Agent 自行扫描磁盘。

### DP-OGC-006 Agent responsibilities

首期扩展现有 `SatelliteAgent`，不新增职责重叠的 `DataPlatformAgent`。Agent 可以分析用户目标、搜索候选影像、解释质量与
覆盖范围、提出发布方案，并在批准后调用修改工具。Agent 不得直接连接 PostgreSQL/PostGIS、拼接对象存储凭证、读取整幅
栅格进上下文、伪造发布成功或自行决定跨项目共享。

### DP-OGC-007 Renderer boundary

WMTS `GetCapabilities`/`GetTile` 和 WMS `GetMap` 由独立 renderer 承担。renderer 只读取 `published` 配置与已引用资产，
负责重投影、采样、颜色映射和瓦片缓存；Gateway 不执行这些像素级操作。首个控制面版本可在 renderer 尚未实现时完成，
但不得把“配置已发布”描述为“OGC 图像服务已可访问”。

## 2. Non-goals

- 首期不复刻参考系统的 URL 形状、字段拼写、正则路径查询或 JMESPath。
- 首期不实现 WMTS/WMS renderer、分布式缓存调度、任意样式脚本和管理后台。
- 首期不新增卫星/传感器专用表，不把 GeoTIFF 存入 PostGIS Raster。
- 首期不新增异步发布任务表；只有确认发布需要跨进程长任务后才设计任务状态机。

## 3. Acceptance

- 五张控制面表可由新增 Alembic 迁移创建，现有 `0011`/`0012` 历史迁移保持不变。
- Layer 只能引用同项目、质量可处理的 catalog asset；Theme 只能引用同 service 的 Layer。
- Gateway 对读取分页、项目隔离、发布状态迁移和乐观并发进行测试。
- SatelliteAgent 的读取工具无需审批，修改工具会进入 HIL，且模型参数中不存在 project/user/run 身份。
- 文档中时间、CRS、bbox 和拼写歧义在接入适配器测试中有确定结果。
- 验收明确区分“控制面发布成功”和“renderer 已提供真实 WMTS/WMS”。
