# Ragas 使用说明

> 本文整理自 [Ragas 官方文档](https://docs.ragas.io/en/stable/)（stable），用于评估 RAG / LLM 应用质量。  
> 适用场景：检索质量、回答忠实度、与标准答案的一致性、Agent 工具调用等。

---

## 1. 是什么

**Ragas**（Retrieval Augmented Generation Assessment）是一套用 **LLM 驱动指标 + 可重复实验** 来评估 AI 应用的库。目标是从“靠感觉试”变成可量化的评估闭环：

```text
改模型/检索/Prompt → 跑同一套评测集 → 看指标变化 → 再迭代
```

能力概览：

| 能力 | 说明 |
|------|------|
| 指标（Metrics） | 对检索、生成、Agent 等维度打分（多数 0–1） |
| 数据集（Dataset） | 统一组织 `user_input` / `retrieved_contexts` / `response` / `reference` |
| 合成测试集 | 从文档自动生成评测问答（Testset Generation） |
| 集成 | LangChain、LlamaIndex、OpenAI / Azure / Bedrock / Gemini 等 |

官方入口：

- 文档首页：<https://docs.ragas.io/en/stable/>
- RAG 快速评估：<https://docs.ragas.io/en/stable/getstarted/rag_eval/>
- 指标列表：<https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>
- 测试集生成：<https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/>

---

## 2. 安装

```bash
pip install ragas
```

若评估时用 LangChain + OpenAI，建议一并安装：

```bash
pip install langchain-openai openai
# 如有版本冲突，可按官方建议固定区间，例如：
# pip install -U "langchain-core>=0.2,<0.3" "langchain-openai>=0.1,<0.2" openai
```

需要最新主分支功能：

```bash
pip install git+https://github.com/vibrantlabsai/ragas.git
```

环境变量（OpenAI 示例）：

```bash
export OPENAI_API_KEY=your-key
```

---

## 3. 核心概念

### 3.1 评测数据字段（现代 API）

跑完你的 RAG 后，每条样本通常包含：

| 字段 | 含义 | 是否必须 |
|------|------|----------|
| `user_input` | 用户问题 | 是 |
| `retrieved_contexts` | 检索到的上下文列表（`list[str]`） | 多数检索类指标需要 |
| `response` | 模型最终回答 | 是（生成类指标） |
| `reference` | 标准答案 / ground truth | 部分指标需要（如 Context Recall、Factual Correctness） |

> 旧教程里常见字段名：`question` / `contexts` / `answer` / `ground_truth`。  
> **新版官方示例统一为上表字段**，写新代码请用新字段名。

### 3.2 评估流程

```text
1. 准备 queries（可选：reference）
2. 用你的 RAG 跑每条 query → 拿到 retrieved_contexts + response
3. 组装 EvaluationDataset
4. 选择 metrics + evaluator LLM
5. evaluate(...) → 得到各指标分数
```

### 3.3 评估器模型 vs 业务模型

- **业务 LLM / 检索**：你的产品链路（生成答案、召回文档）。
- **Evaluator LLM（裁判）**：Ragas 用它给指标打分，建议用较强、较稳的模型（如 `gpt-4o` / `gpt-4o-mini`），并与业务模型分开配置。

---

## 4. 最小可运行示例（评估已有 RAG 输出）

下面不依赖你的真实检索服务，只要有「问题 + 检索上下文 + 回答 + 可选标准答案」即可。

```python
import os

from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import LLMContextRecall, Faithfulness, FactualCorrectness

os.environ.setdefault("OPENAI_API_KEY", "your-key")

# 1) 业务侧：你自己的 RAG 跑完后收集的结果
dataset = [
    {
        "user_input": "Who introduced the theory of relativity?",
        "retrieved_contexts": [
            "Albert Einstein proposed the theory of relativity, "
            "which transformed our understanding of time, space, and gravity."
        ],
        "response": "Albert Einstein introduced the theory of relativity.",
        "reference": (
            "Albert Einstein proposed the theory of relativity, "
            "which transformed our understanding of time, space, and gravity."
        ),
    },
    # ... 更多样本
]

evaluation_dataset = EvaluationDataset.from_list(dataset)

# 2) 裁判模型
evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

# 3) 跑指标
result = evaluate(
    dataset=evaluation_dataset,
    metrics=[
        LLMContextRecall(),
        Faithfulness(),
        FactualCorrectness(),
    ],
    llm=evaluator_llm,
)
print(result)
# 示例输出：
# {'context_recall': 1.0000, 'faithfulness': 0.8571, 'factual_correctness': 0.7280}
```

### 从你的 RAG pipeline 批量收集

```python
dataset = []
for query, reference in zip(sample_queries, expected_responses):
    relevant_docs = rag.get_most_relevant_docs(query)  # list[str]
    response = rag.generate_answer(query, relevant_docs)
    dataset.append(
        {
            "user_input": query,
            "retrieved_contexts": relevant_docs,
            "response": response,
            "reference": reference,
        }
    )
```

---

## 5. 单条指标打分（collections API）

适合调试单条 case，或嵌入自定义评估脚本。官方推荐新项目优先用 collections 风格。

```python
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness

client = AsyncOpenAI()
llm = llm_factory("gpt-4o-mini", client=client)
scorer = Faithfulness(llm=llm)

# 异步
result = await scorer.ascore(
    user_input="When was the first super bowl?",
    response="The first superbowl was held on Jan 15, 1967",
    retrieved_contexts=[
        "The First AFL–NFL World Championship Game was an American football "
        "game played on January 15, 1967, at the Los Angeles Memorial Coliseum."
    ],
)
print(result.value)  # e.g. 1.0

# 同步
# result = scorer.score(user_input=..., response=..., retrieved_contexts=[...])
```

> Legacy API（`SingleTurnSample` + `single_turn_ascore`）仍可用，但官方计划在 0.4 弃用、1.0 移除，新代码尽量别再写。

---

## 6. 常用 RAG 指标说明

分数一般 **0–1，越高越好**（个别指标语义需看文档）。

### 6.1 检索侧（Retriever）

| 指标 | 看什么 | 需要字段（典型） |
|------|--------|------------------|
| **Context Precision** | 检索结果里相关内容是否靠前、噪声是否少 | user_input, retrieved_contexts, reference（或相关标注） |
| **Context Recall** | 标准答案所需信息是否被检索覆盖 | user_input, retrieved_contexts, reference |
| **Context Entities Recall** | 实体级召回 | 视实现而定 |
| **Noise Sensitivity** | 对噪声上下文的敏感度 | 视实现而定 |

### 6.2 生成侧（Generator）

| 指标 | 看什么 | 需要字段（典型） |
|------|--------|------------------|
| **Faithfulness（忠实度）** | 回答是否都能被检索上下文支持（防幻觉） | user_input, response, retrieved_contexts |
| **Response / Answer Relevancy** | 回答是否切题 | user_input, response |
| **Factual Correctness** | 与 reference 的事实一致性 | response, reference |

### 6.3 Faithfulness 怎么算（直觉）

1. 把 `response` 拆成若干 claims  
2. 逐条检查是否能从 `retrieved_contexts` 推断  
3.  
   \[
   \text{Faithfulness} = \frac{\text{被上下文支持的 claims 数}}{\text{claims 总数}}
   \]

例子：

- 问题：Einstein 何时何地出生？  
- 上下文：1879-03-14，德国出生  
- 高分回答：Einstein 1879 年 3 月 14 日生于德国  
- 低分回答：Einstein 1879 年 3 月 **20** 日生于德国 → 日期 claim 无法支持 → 分数下降  

### 6.4 其它指标族（按需）

- **Agent / Tool**：Tool Call Accuracy、Agent Goal Accuracy、Topic Adherence  
- **文本对比**：Semantic Similarity、BLEU / ROUGE / Exact Match  
- **通用打分**：Aspect Critic、Rubrics-based scoring  
- **NVIDIA 系列**：Answer Accuracy、Context Relevance、Response Groundedness  
- **多模态**：Multimodal Faithfulness / Relevance  

完整列表见：  
<https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>

---

## 7. 合成测试集（没有标注数据时）

从知识库文档自动生成问答，降低人工标注成本。

```python
from langchain_community.document_loaders import DirectoryLoader
from langchain_openai import ChatOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.testset import TestsetGenerator
import openai

# 1) 加载文档
loader = DirectoryLoader("your_docs/", glob="**/*.md")
docs = loader.load()

# 2) 生成器 LLM + Embedding
generator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o"))
generator_embeddings = OpenAIEmbeddings(client=openai.OpenAI())

# 3) 生成
generator = TestsetGenerator(
    llm=generator_llm,
    embedding_model=generator_embeddings,
)
testset = generator.generate_with_langchain_docs(docs, testset_size=10)

# 4) 查看 / 导出
df = testset.to_pandas()
print(df.head())
```

内部大致两步：

1. **KnowledgeGraph**：文档 → 节点/关系，并用 transforms 丰富图谱  
2. **Scenario / Query Synthesizers**：按分布生成单跳/多跳等问题  

进阶可自定义 `query_distribution`、保存/加载 `knowledge_graph.json`。  
详见：<https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/>

---

## 8. 自定义裁判模型（非 OpenAI）

Ragas 通过 wrapper 接各种 LLM。LangChain 模型通用写法：

```python
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

evaluator_llm = LangchainLLMWrapper(your_chat_model)
evaluator_embeddings = LangchainEmbeddingsWrapper(your_embeddings)
```

其它常见路径：

| 提供方 | 包装方式 |
|--------|----------|
| OpenAI / Azure OpenAI | `ChatOpenAI` / `AzureChatOpenAI` + `LangchainLLMWrapper` |
| AWS Bedrock | `ChatBedrockConverse` + wrapper |
| Google AI / Vertex | `ChatGoogleGenerativeAI` / `ChatVertexAI` + wrapper |
| LlamaIndex | `LlamaIndexLLMWrapper` |

自定义模型指南：  
<https://docs.ragas.io/en/stable/howtos/customizations/customize_models/>

---

## 9. 指标选型速查

| 你想验证的问题 | 优先指标 |
|----------------|----------|
| 会不会胡编（脱离检索） | **Faithfulness** |
| 检索有没有召到关键材料 | **Context Recall** |
| 检索结果是否干净、排序是否合理 | **Context Precision** |
| 答得是否切题 | **Answer / Response Relevancy** |
| 和标准答案是否一致 | **Factual Correctness** / Semantic Similarity |
| Agent 工具有没有调对 | **Tool Call Accuracy** |

实践建议：

1. 先固定一个 **golden set**（哪怕 20–50 条人工精标）。  
2. 每次改 chunk 大小、embedding、top-k、prompt 时用**同一套指标**对比。  
3. 分清失败来源：检索差 → 调召回；检索好但胡编 → 调生成/约束；都好但文风不对 → 看 Relevancy / 自定义 rubric。  

---

## 10. 和本仓库的关系（multi-agent-s2c）

当前仓库是多 Agent 创作系统（LeaderAgent / SearchAgent / Knowledge 等），**尚未内置 Ragas 评测流水线**。可落地的方向：

1. **Knowledge / 向量检索**  
   - 对 `src/knowledge/` + Milvus 检索：收集 `user_input`、`retrieved_contexts`、`response`。  
   - 用 Faithfulness + Context Recall/Precision 评估知识问答质量。

2. **SearchAgent 参考检索**  
   - 对 `search_references` 返回的 `web_refs` / `knowledge_refs` 做检索侧指标。  
   - 再评估 LeaderAgent 是否忠实使用参考（Faithfulness）。

3. **离线脚本**  
   - 建议放在 `scripts/eval_ragas.py`（或 `test/eval/`），不要塞进在线请求路径。  
   - 评估有 LLM 调用成本与延迟，适合 CI 夜间任务或手动回归，不适合每个 chat 请求实时跑。

示例数据落盘格式（JSONL）：

```json
{
  "user_input": "镜头语言有哪些常见类型？",
  "retrieved_contexts": ["chunk1...", "chunk2..."],
  "response": "常见类型包括……",
  "reference": "标准答案……"
}
```

---

## 11. 常见问题

### Q1：没有 ground truth 能不能评？

可以。**Faithfulness、Answer Relevancy** 等可不依赖 reference；**Context Recall、Factual Correctness** 通常需要 reference。可先无参考指标上线，再逐步补 golden set。

### Q2：分数不稳定？

- 裁判模型 temperature 尽量低（接近 0）。  
- 固定评测集与指标版本。  
- 多样本取均值，不要只看 1–2 条。  

### Q3：成本高？

- 多数指标会对每条样本多次调 LLM。  
- 缩小评测集、降频、换小裁判模型（如 `gpt-4o-mini`），或对部分指标用非 LLM 方案（ROUGE / Exact Match / HHEM 等）。  

### Q4：字段名对不上？

优先使用：`user_input` / `retrieved_contexts` / `response` / `reference`。  
若读到老博客的 `question` / `contexts` / `answer` / `ground_truth`，做一层字段映射即可。

### Q5：`retrieved_contexts` 是字符串还是列表？

应为 **`list[str]`**。单段上下文也要包成列表：`["..."]`。

---

## 12. 推荐阅读顺序

1. 安装：<https://docs.ragas.io/en/stable/getstarted/install/>  
2. 评估简单 RAG：<https://docs.ragas.io/en/stable/getstarted/rag_eval/>  
3. 生成测试集：<https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/>  
4. 指标总览：<https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>  
5. 自定义模型：<https://docs.ragas.io/en/stable/howtos/customizations/customize_models/>  

---

## 13. 参考链接

| 资源 | URL |
|------|-----|
| 官方文档 | https://docs.ragas.io/en/stable/ |
| GitHub | https://github.com/vibrantlabsai/ragas |
| 论文（Ragas） | https://arxiv.org/abs/2309.15217 |
| `evaluate()` API | https://docs.ragas.io/en/stable/references/evaluate/ |

---

*文档生成说明：基于 Ragas stable 文档整理，API 随版本演进；落地前请以官方最新文档为准。*
