# OGC Agent Runtime Slice

关联需求：DP-OGC-005、DP-OGC-006
关联任务：OGC-003

- 扩展现有 SatelliteAgent 的 Gateway tools，不新增职责重叠的 DataPlatformAgent。
- 读取工具只暴露业务查询参数；project/user/run 与凭据从 runtime context 注入。
- 修改工具加入 `HumanInLoopMiddleware` 的明确审批集合；审批展示目标 service/layer/theme、资产数量和预期状态变化。
- Agent 先检索并解释候选数据，再提出发布操作；不得基于模糊地点、缺失时间或无界结果自动发布。
- 工具结果区分 catalog、control plane、renderer 和 cache 状态；Agent 不根据一次成功调用推断其他层成功。
- 影像算法继续委派给已配置 MCP 服务，目录/发布工具不承载像素处理。
