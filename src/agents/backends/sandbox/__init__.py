from .provider_service import (
    SandboxProviderService,
    SandboxState,
    get_sandbox_provider,
    init_sandbox_provider,
    shutdown_sandbox_provider,
)
from .provision_client import SandboxProvision, SandboxProvisionClient

# 在智能体图接线迁移完成前保留旧名称，兼容现有导入。
SandboxProvider = SandboxProviderService

__all__ = [
    "CustomSandbox",
    "SandboxProvider",
    "SandboxProviderService",
    "SandboxProvision",
    "SandboxProvisionClient",
    "SandboxState",
    "S2CSandbox",
    "get_sandbox_provider",
    "init_sandbox_provider",
    "shutdown_sandbox_provider",
]


def __getattr__(name: str):
    if name in {"CustomSandbox", "S2CSandbox"}:
        from .sandbox_backend import CustomSandbox

        return CustomSandbox
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
