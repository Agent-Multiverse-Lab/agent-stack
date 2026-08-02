import importlib
import inspect
from pathlib import Path
from types import ModuleType

from src.agents.base_agent import BaseAgent


class AgentManager:
    def __init__(self) -> None:
        self._instances: dict[str, BaseAgent] = {}
        # FIXME: 单独记录顶层 Agent，避免把内部 subagent 暴露为可创建会话的 Agent。
        self._top_level_ids: set[str] = set()
        self._subagent_ids: set[str] = set()
        self._setup_agent()

    def _setup_agent(self) -> None:
        agent_dir = Path(__file__).parent
        for path in agent_dir.iterdir():
            if not path.is_dir():
                continue
            if path.name in {"__pycache__", "middlewares", "utils", "subagent", "sandbox"}:
                continue

            if path.name == "subagents":
                for sub_path in path.iterdir():
                    if not sub_path.is_dir() or sub_path.name == "__pycache__":
                        continue
                    module = importlib.import_module(
                        f"src.agents.subagents.{sub_path.name}"
                    )
                    self._register_agents_from_module(module, is_subagent=True)
                continue

            module = importlib.import_module(f"src.agents.{path.name}")
            self._register_agents_from_module(module, is_subagent=False)

    def _register_agents_from_module(
        self,
        module: ModuleType,
        *,
        is_subagent: bool,
    ) -> None:
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and obj is not BaseAgent
                and issubclass(obj, BaseAgent)
            ):
                self._instances[name] = obj()
                if is_subagent:
                    self._subagent_ids.add(name)
                else:
                    self._top_level_ids.add(name)

    def get_agent(self, agent_id: str) -> BaseAgent:
        if agent_id in self._instances:
            return self._instances[agent_id]
        raise KeyError(f"Unknown agent: {agent_id}")

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {
                "id": agent_id,
                "name": agent.name,
                "description": agent.description,
            }
            for agent_id, agent in sorted(self._instances.items())
        ]

    def list_top_level_agents(self) -> list[dict[str, str]]:
        # FIXME: 数据库初始化和公开列表必须使用同一份顶层 Agent 清单。
        return [
            {
                "id": agent_id,
                "name": self._instances[agent_id].name,
                "description": self._instances[agent_id].description,
            }
            for agent_id in sorted(self._top_level_ids)
        ]

    def list_subagents(self) -> list[dict[str, str]]:
        """返回内部子智能体注册信息，供启动同步和 Worker 解析使用。"""

        return [
            {
                "id": agent_id,
                "name": self._instances[agent_id].name,
                "description": self._instances[agent_id].description,
            }
            for agent_id in sorted(self._subagent_ids)
        ]


agent_manager = AgentManager()

__all__ = ["agent_manager"]
