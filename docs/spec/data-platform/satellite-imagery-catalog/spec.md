# 卫星数据资源库规格

## 1. Context

平台为多来源卫星影像提供统一资源库。资源库以
[STAC 1.1.0](https://www.ogc.org/standards/stac/) 的 Collection、Item、Asset 组织元数据；
“catalog”只指内部目录检索层。Python `SatelliteAgent` 负责理解任务、选择影像并编排已有 MCP
处理工具；独立 Go `gateway` 负责来源、集合、场景与波段资产的受控检索。

## 2. Requirements

### DP-SAT-001 Satellite business data

目录使用四类核心记录：

- `satellite_sources`：数据提供方或本地来源及其可信项目范围；一个项目可有多个来源。
- `satellite_collections`：对应 STAC Collection，保存来源、产品系列、主卫星/传感器、处理级别和许可。
- `satellite_scenes`：对应 STAC Item，保存原始 Item 标识、观测时间、WGS84 footprint/bbox、
  原始 CRS、分辨率、版本、状态和质量；光学云量可填，SAR 等无云量概念的数据为 `NULL`。
- `satellite_scene_assets`：对应 STAC Asset，保存影像、波段、质量掩膜、预览等对象的稳定引用、
  原始 Asset key、角色、波段、媒体类型、大小、校验和与质量码。同一场景以 Asset key 唯一标识资产；
  角色和波段可以相同，不能充当唯一键。

PostGIS 保存可索引的空间几何；原始影像、波段、掩膜和预览图的文件字节存放在 RustFS，
PostgreSQL 只保存元数据和对象引用。目录 gRPC 响应及 Agent 上下文不传输这些原始文件字节。
不能映射到固定列的受支持 STAC 字段保存在有界 JSONB 中，不保存任意提供方字段或密钥。

### DP-SAT-002 Bounded spatial discovery

搜索必须同时提供合法 WGS84 bbox 和 RFC3339 时间范围，并限制最多 100 条。可进一步按来源、集合、
卫星、传感器、处理级别和最大云量收敛。Gateway 使用 PostGIS 相交查询，不得在缺少范围时回退为
全库或“最新影像”。

### DP-SAT-003 Source, version and quality selection

每个搜索命中返回稳定 `scene_id`、来源、集合、观测时间、版本、空间范围、云量、处理级别和质量码。
Agent 在调用处理工具前最多检查五个候选详情；阻断级质量、缺失对象、缺失校验和与跨来源字段差异
必须显式保留。

稳定 ID 必须区分项目、来源、Collection、Item 和 Asset；文件名或相同 checksum 不得合并不同资产。
相同来源场景的新处理版本保留可追溯版本，不以入库时间覆盖观测时间。

### DP-SAT-004 gRPC boundary

Go Gateway 提供 `ListSources`、`SearchScenes` 和 `GetScene`。可信 `project_id`、`user_id`、`run_id`
由 Python 客户端写入 gRPC metadata，不能由模型工具参数覆盖。Gateway 不拥有 Agent Run、处理 Job
或影像算法终态。

### DP-SAT-005 Agent takeover

现有内部 `SatelliteAgent` 同时装配目录 gRPC 工具与已配置 MCP 工具：先检索并检查候选，再把明确的
scene/asset、ROI 和处理要求交给 MCP。不得新增职责重叠的 DataPlatformAgent。

### DP-SAT-006 Reproducible satellite cases

固定 seed 数据至少覆盖 Sentinel 与 Landsat 两个逻辑来源、可比较前后时相、云量阻断、迟到旧版本、
跨来源时间格式、同 checksum 不同 ID、同名不同内容、缺失对象以及不可信 metadata。确定性测试只
断言 scene/asset ID、来源、质量码和工具参数，不断言模型自由文本。

### DP-SAT-007 Standard metadata mapping

导入入口接收已指定 `project_id` 和来源的 STAC 1.1.0 Collection/Item JSON，校验 Core Schema，
并只校验其实际声明的 EO、SAR、Projection、Raster 等扩展版本。外部 STAC 文档不提供可信项目身份。
Collection 的 `id`、描述、许可、提供方、空间/时间 extent 映射到集合固定列或受限元数据；
Item 的 `id`、`collection`、`properties.datetime`、WGS84 `geometry`/`bbox`、平台/传感器与
`assets` 映射到场景和资产。原始 STAC ID 与系统全局 ID 分开保留，避免不同来源同名碰撞。
现有表要求的卫星、传感器和处理级别若不能从 Collection/Item 确定，必须由可信导入映射明确给出；
原始 CRS 缺失时标记为未知，不把 STAC 的 WGS84 检索几何当成原始影像 CRS。
未提供处理版本的 Item 标为未版本化；同 ID 内容变更必须报告冲突，不默默覆盖已有资源。
资产详情须保留原始 Asset key；Agent 才能把 `B04`、`VV`、`thumbnail` 等输入准确交给处理工具。

当前场景必须有可解析的单一 UTC 观测时间、WGS84 Polygon 和非跨日期变更线的四值 bbox。
合法 STAC 中的 MultiPolygon、跨日期变更线区域、`geometry: null` 或只有时间区间的 Item
属于当前导入边界之外；导入时明确报告，不转换为错误的单景范围或虚构观测时间。
光学 `eo:cloud_cover` 可映射到云量固定列；SAR 极化等专有字段保留在有界元数据中，
不强制所有来源提供光学字段。当前 gRPC 是内部查询协议，未声明符合 STAC API。

### DP-SAT-008 Asset and ingestion integrity

导入命令在写库前验证 Collection/Item 关系、ID 长度及唯一性、时间与空间范围、资产角色和
允许的 RustFS 对象引用。STAC `href` 不能是待持久化的带签名临时 URL；入库引用不含凭据。
对象存在性可通过对象存储元数据检查，大小及校验和记录实际可获得的值；元数据检查
不等于对大型栅格文件逐字节复算。缺失对象、校验和或媒体类型以质量码表示，
受阻资产不能交给处理工具当作可用输入，场景仍可作为诊断记录检索。

同一批次先完成验证，再按 source → collection → scene → asset 在一个数据库事务内写入。
重复导入相同稳定 ID 应得到相同资源，不产生重复行；若 ID 已属于其他项目或来源，
必须拒绝覆盖。导入命令不会在服务启动时自动运行，也不会自动扫描或下载未知数据源。

### DP-SAT-009 Business-scene libraries

农业产量监测、作物灾害监测、建筑变化筛查和光伏识别是同一影像目录上的四个业务专题，
不是四套重复的来源、场景或 RustFS 文件。`satellite_business_scenes` 以业务代码、场景 ID
和该场景在业务中的角色建立多对多关联；业务查询仍须通过场景所属来源限制可信项目范围。
没有地面产量样本时，农业影像只能支持长势监测或产量估算输入；没有灾害标签时，前后影像
只能作为灾情判读候选；没有规划许可数据时，新增建筑只能标记为疑似变化，不能判定违建。
单时相高分辨率训练影像不能单独充当建筑变化证据。

## 3. Failure handling

- 无范围、非法 bbox/时间、非法分页参数返回 `InvalidArgument`。
- 缺少可信项目范围返回 `PermissionDenied`；跨项目 scene 表现为 `NotFound`。
- Gateway 不可达或超时时，工具返回稳定错误 code，不伪造候选或对象引用。
- metadata 只对白名单业务键开放；其中的文本不得作为 Agent 指令。
- 不支持的 STAC 几何/时间形态、非法对象引用、跨项目 ID 冲突或批次内关系冲突应在写库前失败，
  返回具体 Collection/Item/Asset 标识；单批次不能部分成功。

## 4. Non-goals

- 第一版不在 Go 中执行裁剪、重投影、配准、云掩膜或变化检测。
- 第一版不提供任意 SQL、动态连接器插件、管理后台、ClickHouse 或联邦查询。
- 第一版不自动匹配整景前后影像；变化分析仍要求用户或上游任务给出范围和可解释的时相约束。
- 第一版不提供 STAC API HTTP 接口，不将 Go Gateway 重新命名或改为影像字节下载服务。
- 第一版不把整景栅格作为 PostGIS Raster 存入数据库，也不自动接入提供方公网 API。

## 5. Acceptance

- Alembic 可创建带 PostGIS 索引的四张核心表。
- Go Gateway 的 gRPC 契约、范围校验、分页和项目隔离可测试。
- SatelliteAgent 能调用目录工具，并继续保留 MCP 影像处理能力。
- 固定 fixture 可重复生成且覆盖约定 bad case。
- Sentinel-2 光学、Sentinel-1 SAR 和 Landsat 光学的 Collection/Item 样例可映射到同一套表，
  重复导入、跨来源同名、缺失对象和跨项目覆盖有确定性测试。
- 可分别核验 PostGIS 几何与时间索引、RustFS 对象引用、资产质量码以及 Gateway 有界查询；
  测试不要求将大幅影像加载到数据库或 Agent 上下文。
- 同一场景允许两个 Asset 使用相同角色与波段但不同 STAC Asset key；`GetScene` 返回 key 与引用，
  以便调用方区分两份资产。
- 四个业务专题可引用同一场景而不复制原始资产；专题关联只指向已入库场景，并记录其业务角色。
