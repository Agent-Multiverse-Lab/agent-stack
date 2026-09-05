from typing import Any

from src.utils import logger


class AgentRunTimeOut(Exception):
    
    def __init__(agent_run_result: dict[str, Any]):
        agent_status = str(agent_run_result.get("status") or "unknown")
        agent_run_id = str(agent_run_result.get("run_id") or "")
        
        logger.exception(f"当前run_id:{agent_run_id},状态为{agent_status}")
        
        super().__init__(f"agent run： {agent_run_id} 状态为： {agent_status} 挂起")
        
        
    