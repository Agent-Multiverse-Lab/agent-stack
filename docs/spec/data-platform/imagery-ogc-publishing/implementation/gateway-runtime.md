# OGC Gateway Runtime Slice

关联需求：DP-OGC-002、DP-OGC-005、DP-OGC-007
关联任务：OGC-002

- 在现有 Go Gateway 中扩展 publishing service/store；复用认证、project scope、分页和错误映射。
- 读取方法覆盖 service capabilities、layer 列表/详情和 theme 列表；每个列表有稳定排序、游标或边界 limit。
- 修改方法覆盖 layer/theme 创建更新、asset/layer 关联、发布/取消发布和缓存清理命令。
- 发布使用 `expected_version` 条件更新；状态变化与审计字段在一个事务中提交。
- Gateway 返回控制面状态和 renderer 可用性两个独立信号，不把数据库中的 `published` 等同于真实 WMTS/WMS 健康。
- Gateway 不读取整幅栅格、不进行重投影或瓦片渲染，也不在启动时迁移 schema。
