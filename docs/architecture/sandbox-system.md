# Sandbox System Architecture

## 1. Responsibility

提供工具/代码执行隔离边界，避免主应用与外部执行环境混用。

## 2. Deployment Model

- `sandbox_server/` 独立运行，供子代理和工具调用。
- 主服务只通过明确 API 与沙箱服务交互，不在主进程内内嵌沙箱生命周期。

## 3. Runtime Rules

- 沙箱服务可在主请求失败后回收，不影响 run 主流程的持久化状态。
- 主服务不依赖沙箱本地状态做 run 终态决策。
- 沙箱返回错误通过标准化错误码与日志回传给上游服务。

## 4. Security Boundary

- 工具执行、附件渲染、文件读写必须经过沙箱服务。
- 主服务只下发最小参数，不传递敏感会话凭据。
