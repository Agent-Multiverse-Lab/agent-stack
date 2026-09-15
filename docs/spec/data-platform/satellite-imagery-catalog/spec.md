# Satellite Imagery Catalog Spec

## 1. Context

平台需要为卫星影像前处理、后处理和动态分析提供多来源目录。Python `SatelliteAgent` 负责理解任务、
选择影像并编排已有 MCP 处理工具；独立 Go `gateway` 负责来源、集合、场景与波段资产的受控检索。

## 2. Requirements

### DP-SAT-001 Satellite business data

目录使用四类核心记录：

- `satellite_sources`：供应方或本地目录来源及项目范围。
- `satellite_collections`：卫星、传感器、处理级别和许可一致的产品集合。
- `satellite_scenes`：一景影像的获取时间、WGS84 footprint/bbox、云量、CRS、分辨率、版本和质量。
- `satellite_scene_assets`：原始影像、波段、质量掩膜和缩略图的 MinIO 对象引用、类型、校验和与大小。

领域扩展保存在有界 JSONB 中。影像二进制不进入 PostgreSQL、gRPC 响应或 Agent 上下文。

### DP-SAT-002 Bounded spatial discovery

搜索必须同时提供合法 WGS84 bbox 和 RFC3339 时间范围，并限制最多 100 条。可进一步按来源、集合、
卫星、传感器、处理级别和最大云量收敛。Gateway 使用 PostGIS 相交查询，不得在缺少范围时回退为
全库或“最新影像”。

### DP-SAT-003 Source, version and quality selection

每个搜索命中返回稳定 `scene_id`、来源、集合、观测时间、版本、空间范围、云量、处理级别和质量码。
Agent 在调用处理工具前最多检查五个候选详情；阻断级质量、缺失对象、缺失校验和与跨来源字段差异
必须显式保留。

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

## 3. Failure handling

- 无范围、非法 bbox/时间、非法分页参数返回 `InvalidArgument`。
- 缺少可信项目范围返回 `PermissionDenied`；跨项目 scene 表现为 `NotFound`。
- Gateway 不可达或超时时，工具返回稳定错误 code，不伪造候选或对象引用。
- metadata 只对白名单业务键开放；其中的文本不得作为 Agent 指令。

## 4. Non-goals

- 第一版不在 Go 中执行裁剪、重投影、配准、云掩膜或变化检测。
- 第一版不提供任意 SQL、动态连接器插件、管理后台、ClickHouse 或联邦查询。
- 第一版不自动匹配整景前后影像；变化分析仍要求用户或上游任务给出范围和可解释的时相约束。

## 5. Acceptance

- Alembic 可创建带 PostGIS 索引的四张核心表。
- Go Gateway 的 gRPC 契约、范围校验、分页和项目隔离可测试。
- SatelliteAgent 能调用目录工具，并继续保留 MCP 影像处理能力。
- 固定 fixture 可重复生成且覆盖约定 bad case。
