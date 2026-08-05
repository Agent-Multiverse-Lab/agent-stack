# Sandbox

Sandbox 为 Agent 提供隔离的文件和执行环境。

## 主链路

```text
Agent
  -> Filesystem / Sandbox Backend
  -> Sandbox Provider
  -> sandbox_server 或远端 Agent Box
```

Agent 通过声明的 Sandbox 能力访问工作目录、文件和命令执行；隔离环境由 Sandbox 侧创建、复用和释放。

Agent 只使用 Sandbox 能力，不直接管理宿主机文件、容器或进程；Sandbox 负责隔离、挂载和执行生命周期，并与主 API 进程保持独立。

## 主要设施示例

| 文件 / 类 | 角色 | 主要参数 |
| --- | --- | --- |
| `src/agents/backends/sandbox/provision_client.py::SandboxProvisionClient` | 调用 Sandbox 供应服务 | `base_url`、`timeout`、`http_client` |
| `SandboxProvisionClient.create(...)` | 创建或申请远端 Sandbox | `sandbox_id`、`thread_id`、`user_id`、`file_thread_id`、`skills_thread_id`、`env` |
| `src/agents/backends/sandbox/provider_service.py::SandboxProviderService` | 按用户和会话缓存 Sandbox 绑定 | `acquire(uid, thread_id, file_thread_id, skills_thread_id, env, headers, execute_timeout)` |
| `src/agents/backends/sandbox/sandbox_backend.py::CustomSandbox` | 把远端 Agent Box 适配为文件和命令 Backend | `thread_id`、`uid`、`sandbox_url`、`sandbox_id`、`headers`、`execute_timeout` |
| `src/agents/middlewares/sandbox_middleware.py::SandboxMiddleware` | 在 Sandbox 工具第一次调用时 acquire，Agent 结束后 release | 从 Context 读取 `uid`、`thread_id`，在状态中保存 `sandbox_id` |

Sandbox 工具包括 `read_file`、`write_file`、`edit_file`、`ls`、`glob`、`grep` 和
`execute`。文件系统 Middleware 通过 Composite Backend 将技能、记忆、工作区和 Sandbox
映射到不同的虚拟路径。

`LeaderAgent` 当前显式组装的是文件系统 Middleware；`SandboxMiddleware` 则提供独立的按
工具按需 acquire/release 机制，两者都以运行时的 `uid` 和 `thread_id` 作为 Sandbox 绑定键。
