# Resume 接线实施任务

状态：本轮接线实施与定向验证完成。计划见 plan.md v0.3.0；完整能力的真实服务联调未执行。

- [x] T1（RUN-HIL-002 至 004、007）：接入 answers 请求与校验、幂等回答比较、父模型配置传递。
- [x] T2（RUN-HIL-005、007、008）：补齐恢复入口参数、checkpoint 验证、现有 handler 调用和消息保存接线。
- [x] T3（RUN-HIL-005、006、009）：Worker 传递 answers，接收 handler 原有字段并调用既有终态函数；普通入口暂存中断 chunk，保存 checkpoint 后再发出并依据 interrupted 返回。
- [x] T4（RUN-HIL-009 至 011）：前端多题单选、answers 提交、事件与刷新恢复。
- [x] T5：19 个定向测试、前端构建、模拟 API 的浏览器核验、源码编译与受保护函数差异检查通过；证据及范围外限制见 plan.md。
