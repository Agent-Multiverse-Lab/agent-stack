# Agent Runtime Slice

关联需求：DP-SAT-003、DP-SAT-004、DP-SAT-005  
关联任务：SAT-003

- `src/third_party/satellite_gateway/` 保存生成客户端和小型 async 边界。
- 目录工具为 `list_satellite_sources`、`search_satellite_scenes`、`inspect_satellite_scenes`。
- 搜索工具要求 bbox 与时间；详情工具最多接收五个 scene ID，并裁剪资产数量和 metadata 白名单。
- `SatelliteAgent.get_agent()` 同时装配目录工具与 `get_mcp_tools()` 返回的处理工具。
- Gateway 地址、项目范围与超时来自服务端配置，不暴露为模型参数。
