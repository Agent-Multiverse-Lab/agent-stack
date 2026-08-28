from abc import abstractmethod
from dataclasses import asdict, is_dataclass
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.types import Command

from src.database import postgres_manager
from src.utils.logger import logger

from .base_context import BaseContext


def unpack_data(data: Any) -> Any:
    """拆解Tool输出内容

    Args:
        data (Any): _description_

    Returns:
        Any: _description_
    """
    if data is None or isinstance(data, (str, int, float,bool)):
        return data

    if isinstance(data, dict):
        return {key: unpack_data(value) for key, value in
        data.items()}

    if isinstance(data, (list, tuple, set)):
        return [unpack_data(value) for value in data]

    if is_dataclass(data):
         return unpack_data(asdict(data))

    if hasattr(data, "__dict__"):
        return {
            key: unpack_data(value)
            for key, value in vars(data).items()
            if not key.startswith("_")}

    return data

class BaseAgent:
    name: str = "base_agent"
    description: str = ""
    agent_context: type[BaseContext] = BaseContext

    def __init__(self, **kwargs):
        self.agent = None

    def get_store(self) -> AsyncPostgresStore:
        '''获取当前进程已初始化的 LangGraph Store。'''

        return postgres_manager.get_langgraph_store()

    def get_checkpointer(self) -> AsyncPostgresSaver:
        '''获取当前进程已初始化的 LangGraph Checkpointer。'''

        return postgres_manager.get_langgraph_checkpointer()

    @property
    def module_name(self):
        return self.__class__.__name__

    def id(self):
        return f"{self.module_name}_{self.name}"

    @abstractmethod
    async def get_agent(self, context: BaseContext) -> CompiledStateGraph:
        pass

    async def stream_messages(
        self, messages: list[str], runtime_context=None, **kwargs
    ):
        """纯异步流失输出之用，测试

        Args:
            messages (list[str]): 输入的对话内容
            runtime_context (_type_, optional): 当前agent执行的上下文

        Yields:
            _type_: _description_
        """

        context: BaseContext = self.agent_context()
        context.update_context(runtime_context or {})
        agent: CompiledStateGraph = await self.get_agent(context)
        async for mode, chunk in agent.astream(
            messages,
            config=runtime_context,
            stream_mode=["messages"],
            **kwargs,
        ):
            if mode == "messages":
                yield mode, chunk[0]
            else:
                yield mode, chunk

    async def stream_messages_with_event(
        self, messages: list[str], runtime_context=None, **kwargs
    ):
        """使用lanchain 的stream as event 方法输出内容，以便形成可观测的输出模式

        Args:
            messages (list[str]): 输入消息
            runtime_context (_type_, optional): 当前运行所需的上下文， 可能包含agent的仍和配置

        """

        # 配置上下文
        context: BaseContext = self.agent_context()
        context.update_context(runtime_context or {})
        agent: CompiledStateGraph = await self.get_agent(context)
        logger.info(f"智能体：{agent} 初始化成功")

        # 配置运行中的 configuarable 参数， 具体可看 agent 的stream方法
        input_config = {
            "configurable": {"thread_id": context.thread_id, "uid": context.uid}
        }

        # TODO
        # 需要加上 langfuse callback 的调度器，这里不写

        # 以 v3 的形式返回，主要是看看效果啥样
        async with await agent.astream_events(
            input={"messages": messages},
            config=input_config,
            version="v3",
            context=context,
            **kwargs,
        ) as stream_events:  # ty:ignore[no-matching-overload]
            async for stream_event in stream_events:
                stream_methods = stream_event.get("method")
                stream_params = stream_event.get("params")
                stream_data = stream_params.get("data") #此处根据方法不同，内容也不同, 具体得自己debug看下，随便写个就知道了
                stream_namesapce = stream_params.get("namespace", []) # 当有旁路子图或者agent执行时，namespace会有东西
                
                if stream_methods == "values":
                    # 返回直接参数，由于values的特殊性，其返回的时候，只有完全参数提取的时候才出现 value,即是一个完整消息，
                    # 输出的时候，直接返回就可跳过了，只有values是完整的，其他的都是流式的
                    yield stream_methods, stream_data
                    continue
                

                if stream_methods == "messages":
                    # 输出的 stream_data 在 messages 执行中分为好几个部分，
                    # 头一段会生成event事件，其中包含delta的模型产生的流式数据
                    # 后一部分会生成langchain的初始化数据，包含langraph的执行路径， 等等一堆元数据
                    stream_msg, stream_agent_run_metadata = stream_data
                    
                    # purely 上面二参数
                    stream_agent_run_metadata = dict(stream_agent_run_metadata or {})
                    
                    # 添加额外数据,因为会添加子图（子agent）的关系，此处需要保留
                    stream_agent_run_metadata["namespace"] = stream_namesapce
                    
                    # TODO 添加额外的验证以及需要填充的参数
                    
                    # 返回的数据可能都会有用
                    yield stream_methods, (stream_msg, stream_agent_run_metadata)
                    
                    
                if stream_methods == "tool":
                    # 对 tool 消息进行清洗
                    stream_execute_data = {
                        "stream_methods": stream_methods,
                        "stream_namesapce": stream_namesapce,
                        "stream_data":stream_data
                    }
             
                    # 构建任务触发时，所要输出内容
                    yield "agent_execute_event", stream_execute_data

    # FIXEME: Resume 必须把 Command 原样交给 LangGraph，不能包装成 messages。
    async def stream_message_by_resume(
        self,
        resume_input: Command,
        runtime_context=None,
        **kwargs,
    ):
        context: BaseContext = self.agent_context()
        context.update_context(runtime_context or {})
        agent: CompiledStateGraph = await self.get_agent(context)
        logger.info(f"智能体：{agent} Resume 初始化成功")
        input_config = {
            "configurable": {"thread_id": context.thread_id, "uid": context.uid}
        }

        async with await agent.astream_events(
            input=resume_input,
            config=input_config,
            version="v3",
            context=context,
            **kwargs,
        ) as stream_events:  # ty:ignore[no-matching-overload]
            async for stream_event in stream_events:
                stream_method = stream_event.get("method")
                stream_params = stream_event.get("params") or {}
                stream_data = stream_params.get("data")
                stream_namespace = stream_params.get("namespace", [])

                if stream_method == "values":
                    yield stream_method, stream_data
                    continue

                if stream_method == "messages":
                    stream_msg, stream_agent_run_metadata = stream_data
                    stream_agent_run_metadata = dict(
                        stream_agent_run_metadata or {}
                    )
                    stream_agent_run_metadata["namespace"] = stream_namespace
                    yield stream_method, (
                        stream_msg,
                        stream_agent_run_metadata,
                    )
                    continue

                if stream_method == "tool":
                    yield "agent_execute_event", {
                        "stream_methods": stream_method,
                        "stream_namesapce": stream_namespace,
                        "stream_data": stream_data,
                    }
