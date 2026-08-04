from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MilvusConfig(BaseSettings):
    """Milvus 知识库配置。"""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    uri: str = Field(
        default="",
        validation_alias="MILVUS_URI",
        description="Milvus 连接地址",
    )
    token: str = Field(
        default="",
        validation_alias="MILVUS_TOKEN",
        description="Milvus 访问令牌",
    )
    db_name: str = Field(
        default="",
        validation_alias="MILVUS_DB_NAME",
        description="Milvus 数据库名称",
    )


class Config(BaseSettings):
    """配置管理: 环境变量 > .env > 代码默认值"""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 存储 ----------
    save_dir: str = Field(default="./save", description="生成产物的存储目录")
    model_location: str = Field(default="./model", description="本地模型存放目录")

    # ---------- 模型 ----------
    default_model: str = Field(
        default="deepseek/deepseek-v4-pro", description="默认使用的模型名称"
    )
    fallback_model: str = Field(
        default="deepseek/deepseek-v4-pro", description="备用模型名称"
    )
    flash_model: str = Field(
        default="deepseek/deepseek-v4-flash", description="快速推断模型名称"
    )
    image_model: str = Field(default="qwen/qwen-image-2.0-pro-2026-04-22", description="图片生成模型名称")

    
    embed_model: str = Field(
        default="",
        description="向量生成模型名称，格式为 provider/model",
    )
    rerank_model: str = Field(
        default="",
        description="重排序模型名称，格式为 provider/model",
    )
    dashscope_rerank_url: str = Field(
        default="",
        description="DashScope Rerank 完整请求地址",
    )
    rerank_request_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Rerank 单次请求超时秒数",
    )
    rerank_candidate_limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="启用 Rerank 时的初召回候选数量",
    )

    # ---------- Agent ----------
    hil_approval_tools: tuple[str, ...] = Field(
        default=("write_file", "edit_file", "execute"),
        min_length=1,
        max_length=3,
        description="需要人工审批的工具名称（1-3 个）",
    )

    # ---------- 数据库 ----------
    database_url: str = Field(default="", description="PostgreSQL 数据库连接地址")
    langgraph_database_url: str = Field(
        default="", description="LangGraph PostgreSQL 连接地址"
    )
    redis_url: str = Field(default="redis://8.136.2.212:6379/0", description="Redis 连接地址")
    arq_queue_name: str = Field(default="agent-runs", description="ARQ 队列名称")
    arq_max_jobs: int = Field(default=64, description="ARQ worker 最大并发任务数")
    enable_run_queue: bool = Field(default=False, description="是否使用 ARQ/Redis 执行 agent run")
    redis_pool_max_connections: int = Field(default=20, description="Redis 连接池最大连接数")
    run_stream_poll_timeout_ms: int = Field(
        default=15000, description="Redis Stream 阻塞读取超时时间"
    )
    run_stream_max_len: int = Field(default=10000, description="单个 run 事件流保留长度")

    # ---------- JWT ----------
    jwt_secret: str = Field(default="", description="JWT 签名密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT 加密算法")
    jwt_expire_minutes: int = Field(default=60, description="Token 有效期（分钟）")

    # ---------- MinIO ----------
    minio_endpoint: str = Field(default="", description="MinIO 服务地址")
    minio_access_key: str = Field(default="", description="MinIO Access Key")
    minio_secret_key: str = Field(default="", description="MinIO Secret Key")
    attachment_bucket: str = Field(
        default="attachments",
        description="用户附件私有 Bucket",
    )

    # ---------- 知识库 ----------
    milvus: MilvusConfig = Field(
        default_factory=MilvusConfig,
        description="Milvus 知识库配置",
    )

    # ---------- Search ----------
    tavily_api_key: str = Field(default="", description="Tavily Web Search API Key")
    search_max_concurrency: int = Field(default=4, description="并行搜索最大任务数")
    search_route_timeout_seconds: float = Field(default=8.0, description="单路搜索超时时间")
    local_reference_root: str = Field(default="", description="本地参考资料搜索根目录")

    # ---------- MCP ----------
    mcp_servers: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="MCP 服务器连接配置",
    )
    mcp_connect_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        description="MCP 服务器连接和工具发现超时时间",
    )
    mcp_tool_call_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        description="MCP 工具调用超时时间",
    )
    mcp_max_concurrency: int = Field(
        default=16,
        ge=1,
        description="单进程 MCP 工具最大并发调用数",
    )

    # ---------- Document Parser APIs ----------
    mineru_api_url: str = Field(default="", description="MinerU parsing API URL")
    mineru_api_key: str = Field(default="", description="MinerU parsing API key")
    tika_server_url: str = Field(default="", description="Apache Tika Server URL")
    paddle_ocr_api_url: str = Field(default="https://paddleocr.aistudio-app.com/api/v2/ocr/jobs", description="PaddleOCR parsing API URL")
    paddle_ocr_api_key: str = Field(default="", description="PaddleOCR parsing API key")
    unlimited_ocr_api_url: str = Field(
        default="https://aip.baidubce.com/rest/2.0/brain/online/v2/unlimited-ocr-parser/task",
        description="百度 Unlimited-OCR 任务提交接口",
    )
    unlimited_ocr_api_key: str = Field(
        default="",
        description="百度 Unlimited-OCR API Key",
    )
    unlimited_ocr_secret_key: str = Field(
        default="",
        description="百度 Unlimited-OCR Secret Key",
    )
    unlimited_ocr_poll_interval_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Unlimited-OCR 任务轮询间隔",
    )
    unlimited_ocr_poll_timeout_seconds: float = Field(
        default=600.0,
        gt=0,
        description="Unlimited-OCR 任务轮询超时时间",
    )
    document_parser_api_timeout_seconds: float = Field(
        default=120.0, description="Document parser API request timeout"
    )

    # ---------- Sandbox ----------
    sandbox_provider: str = Field(default="provisioner", description="沙箱提供者")
    sandbox_provisioner_url: str = Field(
        default="http://localhost:8002",
        validation_alias="SANDBOX_PROVISIONER_URL",
        description="沙箱供应服务地址",
    )
    sandbox_volume_path: str = Field(default="/home/sandbox/data", description="Sandbox provisioner service URL")
    sandbox_execute_timeout: int = Field(default=180, description="执行最长时间")
    andbox_keepalive_interval_seconds: int = Field(default=30, description="沙箱生命周期")

    # ---------- Langfuse ----------
    langfuse_public_key: str = Field(default="", description="Langfuse Public Key")
    langfuse_secret_key: str = Field(default="", description="Langfuse Secret Key")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse 服务地址"
    )
    langfuse_tracing_enabled: bool = Field(default=False, description="是否启用 Langfuse tracing")
    langfuse_tracing_environment: str = Field(default="development", description="Langfuse 环境")

    # ---------- API Keys ----------
    dashscope_api_key: str = Field(default="", description="阿里 DashScope API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    gemini_api_key: str = Field(default="", description="Gemini API Key")
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")


config = Config()
