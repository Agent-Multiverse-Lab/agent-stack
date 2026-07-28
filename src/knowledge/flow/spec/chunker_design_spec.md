# Knowledge Flow Chunker 设计 SPEC

> 状态：设计初稿，供评审；本文暂不代表已经完成的实现。
>
> 参考实现：`/home/leejuju/projects/ragflow/rag/flow/chunker/`
>
> 参考快照：RAGFlow `2589b6e26d00`。该目录是生产 DSL Chunker 源码，不是 RAGFlow
> 已有的 SPEC。

## 1. 目标

本文只设计 `src/knowledge/flow/chunker/` 的职责、输入输出和切分策略。Parser 只额外保留
Plain PDF 已产生的 JSON 中间态和原文件来源，Extractor、向量化、数据库与知识库写入
流程不在本文范围内。

首版保留三个明确能力：

1. `TokenChunker`：按固定 token 步长切分。
2. `GroupTitleChunker`：按标题段落分组，同一段落内尽量合并。
3. `HierarchyTitleChunker`：按标题层级建立树，并保留完整标题路径。
4. `resolve_outline_levels`：使用 PDF 原始大纲为解析后的 JSON 内容补充标题层级。

`TitleChunker` 只是 `group` 和 `hierarchy` 两种标题策略的统一入口，不再实现第三套切分
算法。

## 2. RAGFlow 参考实现结论

RAGFlow 当前目录结构为：

```text
rag/flow/chunker/
├── schema.py
├── token_chunker.py
└── title_chunker/
    ├── common.py
    ├── schema.py
    ├── title_chunker.py
    ├── group_chunker.py
    └── hierarchy_chunker.py
```

它的公共链路是：

```text
Parser 的多种输出
  -> FromUpstream Pydantic 校验
  -> 统一为内部 text/table/image 记录
  -> TokenChunker 或 TitleChunker
  -> list[dict] chunks
  -> 恢复 PDF 预览文本与坐标
```

### 2.1 TokenChunker

RAGFlow 的 `TokenChunker` 不只有“固定 token”一种行为，还包含：

- `token_size`：按 token 大小合并；
- `delimiter`：按自定义分隔符切分；
- `one`：整篇作为一个 chunk；
- overlap；
- table/image 前后文补充；
- `children_delimiters` 二次切分，并用 `mom` 保存父文本；
- PDF 坐标合并和预览文本恢复。

这些能力适用于 RAGFlow 的通用 DAG 和统一 JSON 输入，但不应该一次性全部复制到当前
项目。

它的 `token_size` 也不是严格的固定步长：结构化输入按 Parser records 合并，单条超长
record 不会继续切开，因此 token 大小可能超过配置值；delimiter 路径则直接绕过 token
大小合并。当前项目只参考它的职责拆分，不照搬这些边界行为。

### 2.2 TitleChunker

当前实现按 RAGFlow 的职责拆分统一解析每一行的标题层级：

```text
TitleChunker._invoke()
  -> HierarchyTitleChunker.invoke() 或 GroupTitleChunker.invoke()
  -> BaseTitleChunker.invoke()
  -> resolve_levels()
  -> resolve_title_levels()
     -> resolve_outline_levels()：优先使用 bigram 匹配 PDF outline
     -> resolve_frequency_levels()：无有效 outline 时按正则族命中频率退避
```

层级确定后再选择：

- `group`：按目标标题层级生成 section，同 section 内合并文本；
- `hierarchy`：构建标题树，沿标题路径生成 chunk。

RAGFlow 的 Group 策略还硬编码了 `32` 和 `1024` 两个 token 阈值。Hierarchy 策略支持
`include_heading_content`、`root_chunk_as_heading` 等行为。

其中 Group 在当前 chunk 小于 32 tokens 时允许跨 section 吸收下一条，1024 也不是
严格上限；Hierarchy 本身没有对超长结果再次做 token 切分。这些都与当前项目希望的
“不跨 section、统一受 `chunk_token_size` 控制”不同。

## 3. 当前项目的设计边界

当前项目仍把所有文档归一化为 Markdown 和 `DocumentBlock`。Plain PDF 同时保留 Parser
已经读出的 JSON 页面中间态，供 TitleChunker 解析大纲层级：

```text
任意文档
  -> Parser
  -> ParsedDocument(Markdown + blocks)
Plain PDF
  -> ParsedDocument.json_result + file_source
  -> resolve_outline_levels
  -> Chunker
  -> list[DocumentChunk]
```

Chunker 仍只接受一种稳定输入 `ParsedDocument`。它不直接处理：

- Parser 的 suffix 分发或解析引擎选择；
- HTML、Markdown 等多种上游接口；
- OCR、版面识别或 PDF Canvas；
- 向量、索引或持久化。

只有 `BaseTitleChunker.extract_line_records(document)` 会读取
`document.json_result`；`resolve_outline_levels(...)` 使用 Parser 已写入
`document.outlines` 的结果。Group 和 Hierarchy 不直接读取文件或 JSON。

### 3.1 输入

```python
ParsedDocument(
    name: str,
    suffix: str,
    markdown: str,
    blocks: list[DocumentBlock],
    metadata: dict,
    json_result: list[dict] | None,
    file_source: str | bytes | Path | None,
)
```

`json_result` 和 `file_source` 是 `ParsedDocument` 的专用字段，不放进 metadata，避免
整份 PDF 内容被复制到每个 chunk。

每个 `DocumentBlock` 至少包含：

```python
DocumentBlock(
    text: str,
    kind: Literal["text", "title", "table", "image"],
    heading_level: int | None,
    metadata: dict,
)
```

### 3.2 输出

所有 Chunker 统一返回：

```python
list[DocumentChunk]
```

每个 `DocumentChunk` 至少包含：

```python
DocumentChunk(
    text: str,
    kind: Literal["text", "title", "table", "image"],
    metadata: dict,
)
```

首版不再增加 RAGFlow 的 `FromUpstream` Schema。当前项目已经有明确的数据类，再套一层
Pydantic 只会重复表达同一份契约。

## 4. 目录设计

```text
src/knowledge/flow/chunker/
├── __init__.py
├── common.py
├── token_chunker.py
└── title_chunker/
    ├── __init__.py
    ├── title_chunker.py
    ├── group_chunker.py
    └── hierarchy_chunker.py
```

各文件职责：

| 文件 | 职责 |
| --- | --- |
| `common.py` | 文本归一化、token 计数、固定步长切分、来源 metadata 汇总和 PDF outline 层级解析 |
| `token_chunker.py` | 实现固定 token 步长切分 |
| `title_chunker/title_chunker.py` | 根据 `method` 精确分发到 group 或 hierarchy |
| `title_chunker/group_chunker.py` | 以目标标题为 section 边界，在 section 内合并 |
| `title_chunker/hierarchy_chunker.py` | 构建标题树，生成带完整标题路径的 chunks |

首版不增加注册表、Factory、BaseChunker、Schema 文件或单独的配置类。

## 5. 公共配置

Chunker 只暴露实际会影响切分结果的参数：

```python
TokenChunker(
    chunk_token_size=512,
)

TitleChunker(
    method="group" | "hierarchy",
    target_level=3,
    chunk_token_size=512,
)
```

Pipeline 的入口保持：

```python
await DocumentFlow.run(
    ...,
    chunker="token" | "title",
    title_method="group" | "hierarchy",
    target_level=3,
    chunk_token_size=512,
)
```

默认链路：

```text
DocumentFlow
  -> TitleChunker(method="hierarchy")
  -> target_level=3
  -> chunk_token_size=512
```

参数约束：

- `chunk_token_size > 0`；
- `target_level > 0`；
- 不支持的 `chunker` 或 `method` 立即报错；
- 首版不暴露 overlap、delimiter、children delimiter、media context 等参数。

## 6. TokenChunker

### 6.1 处理规则

```text
按原顺序遍历 blocks
  -> 连续的 title/text blocks 放入正文缓冲区
  -> table/image 出现时先刷新正文缓冲区
  -> table/image 独立成为原子 chunk
  -> 文档结束时刷新剩余正文
```

正文缓冲区的文本按固定 `chunk_token_size` 连续切分：

- 不重叠；
- 不优先寻找句号或换行；
- 不丢字；
- 不改变 block 顺序；
- 一个 chunk 可以覆盖多个相邻来源 block；
- 一个超长 block 可以被拆成多个 chunk。

### 6.2 Token 计算

优先使用本地已经存在且哈希正确的 `cl100k_base` 缓存。缓存不存在时使用确定、可逆、
不联网的离线近似：

- 中日韩统一表意文字按单字计算；
- 其他字符按最多四个 UTF-8 字节组合；
- 不在 Unicode 码位中间截断。

这个规则的目的不是模拟某个 Embedding 模型的精确 tokenizer，而是保证离线测试、
中文切分和生产运行结果稳定。

### 6.3 暂不照搬 RAGFlow 的能力

以下能力保留为后续候选，不进入首版：

| 能力 | 暂不进入首版的原因 |
| --- | --- |
| `delimiter_mode` | 当前需求明确是固定步长 |
| overlap | 会增加重复内容和 metadata 合并复杂度 |
| `children_delimiters` / `mom` | 当前没有父子检索契约 |
| table/image context | 当前表格和图片应保持原子，是否拼上下文需由检索策略决定 |
| `one` 模式 | 调用方可直接使用完整 Markdown，没有必要做 Chunker 特例 |

## 7. 标题层级来源

标题策略按以下顺序取得结构：

```text
已有 Markdown 标题
  -> 直接使用 DocumentBlock.kind/heading_level
Plain PDF JSON
  -> resolve_outline_levels(document)
  -> extract_pdf_outline(document.file_source)
  -> 逐项读取行级 JSON list
  -> 按文本匹配大纲标题
  -> 命中行转成 title + heading_level
```

`resolve_outline_levels` 和 `resolve_frequency_levels` 放在
`chunker/title_chunker/common.py`。Group 和 Hierarchy 都继承
`BaseTitleChunker.invoke()`，只覆盖 `resolve_levels()` 与 `build_chunks()`。

PDF outline 的 depth 从 0 开始，转换成 `heading_level` 时统一加 1：

```text
depth=0 -> heading_level=1
depth=1 -> heading_level=2
depth=2 -> heading_level=3
```

同一 depth 的第一章、第二章、第三章保持同级。匹配时先做空白和全角空格归一化，依次
使用精确匹配、受长度约束的前缀匹配和 0.8 的二元字符相似度。Plain 的 `position`
当前固定为空，因此只能在整份行列表中匹配；每个 outline 候选最多消费一次。未命中的
行保持普通正文。

### 7.1 Plain PDF 的已知限制

Plain PDF 只通过 `pypdf` 读取原生文字层，通常不能识别字号。标题层级只在 PDF 自带
outline 且 outline 标题能在对应页文本中匹配时恢复：

```text
Plain PDF 行级 JSON list
  -> PDF 有 outline 且标题命中
  -> 生成 title blocks
  -> Group/Hierarchy 按层级切分

PDF 没有 outline 或没有任何标题命中
  -> 保留原 ParsedDocument
  -> 退化为普通 token 切分
```

Plain PDF JSON 不生成 `## Page N` 页面标记。

标题解析优先级为：

1. Parser 原生输出的 Markdown 标题；
2. PDF outline；
3. OCR/layout 给出的 title、section、head 标签；
4. 从 RAGFlow 标题正则族中选择全文命中次数最多的一组；
5. 全部未命中时保持正文，不猜标题。

## 8. GroupTitleChunker

Group 的目标是“同一标题段落尽量合并”，不是构建多层父子文档。

### 8.1 Section 边界

遍历标题时维护标题栈。遇到：

```text
kind == "title" 且 heading_level <= target_level
```

立即结束上一个 section，并以该标题开始新 section。

更深的标题仍然属于当前 section，可以进入正文和标题 metadata，但不打断目标 section。

### 8.2 Section 内切分

```text
一个 section
  -> 收集连续 title/text blocks
  -> table/image 出现时刷新正文
  -> 正文超过 chunk_token_size 时复用 TokenChunker
  -> 不跨 section 合并
```

与 RAGFlow 不同，首版不硬编码 `MIN_GROUP_TOKENS=32` 和
`MAX_GROUP_TOKENS=1024`。最大大小统一由 `chunk_token_size` 控制，避免出现两套大小
配置。

每个输出 chunk 写入：

```python
metadata["heading_path"] = ["一级标题", "二级标题", ...]
metadata["heading_level"] = 当前 section 标题级别
```

没有标题时，整篇文档视为根 section，按 TokenChunker 切分。

## 9. HierarchyTitleChunker

Hierarchy 的目标是保留父子标题关系，并让每个叶子内容知道完整上下文路径。

### 9.1 构树

使用栈按 `heading_level` 构建树：

```text
root
├── H1
│   ├── H2
│   │   └── 正文
│   └── H2
│       └── 正文
└── H1
    └── 正文
```

只把 `heading_level <= target_level` 的标题变成树节点。更深标题作为当前节点的普通内容，
不能丢失。

父标题下面直接出现、但不属于任何子标题的正文也必须输出。

### 9.2 生成 chunk

每个节点按文档顺序处理：

1. 累积当前节点直属的 title/text；
2. 遇到子节点前刷新直属正文；
3. 递归处理子节点；
4. table/image 独立输出，但继承当前标题路径；
5. 空标题节点至少生成一个只包含标题路径的 chunk。

输出正文默认包含标题路径：

```text
一级标题
二级标题
当前正文
```

同时写入：

```python
metadata["heading_path"] = ["一级标题", "二级标题"]
metadata["heading_level"] = 2
```

标题路径本身占用 `chunk_token_size` 预算，正文只能使用剩余 token，保证最终 chunk 大小
接近配置值。

### 9.3 `target_level` 语义

当前项目的 `target_level` 表示真实 Markdown 标题级别，例如：

```text
target_level=3 -> H1、H2、H3 可以成为树节点
```

不照搬 RAGFlow“在实际出现的标题级别中取第 N 个”的序号语义，避免同一配置在不同文档
上表示不同层级。

## 10. 表格和图片

`table` 和 `image` 都是原子块：

- 不参与普通正文拼接；
- 不按 token 从中间切开；
- 保持原始顺序；
- 在 Group/Hierarchy 中继承当前 `heading_path`；
- 继承自身来源 metadata。

首版不自动把上下文正文复制到表格或图片 chunk。需要上下文时，检索端可以结合
`heading_path`，或后续明确引入 media context 配置。

## 11. 来源 Metadata

当前 `block_metadata=[{"page": 1}, {"page": 1}, ...]` 可读性差，也会产生大量重复。
建议 Chunker 输出时将来源信息压缩为：

```python
metadata = {
    "heading_path": ["诊疗指南", "治疗"],
    "heading_level": 2,
    "pages": [12, 13],
}
```

规则：

- `pages` 按首次出现顺序去重；
- 只有真实页码时才写入；
- 不制造默认 `page=1`；
- 页码不进入标题路径；
- block 上除页码以外的有效来源字段才进入 `source_blocks`；
- 完全相同的来源 metadata 只保留一次。

如果后续 Parser 提供 PDF 坐标，则另行定义现有 `position` 字段的稳定值结构；不直接
复制 RAGFlow 与 Canvas 绑定的内部字段。

## 12. 与 RAGFlow 的取舍

| 维度 | RAGFlow | 当前项目设计 |
| --- | --- | --- |
| 输入 | markdown/text/html/json/chunks 多种格式 | 只接收 `ParsedDocument` |
| 输入校验 | Pydantic `FromUpstream` | Python 数据类契约 |
| 标题识别 | outline、正则、layout | Markdown 标题 + PDF outline，不做正则/layout fallback |
| Token 模式 | token、delimiter、one | 首版只做固定 token |
| overlap | 支持 | 首版不支持 |
| Group 大小 | 固定 32/1024 阈值 | 统一使用 `chunk_token_size` |
| Hierarchy 层级 | 实际层级的第 N 档 | 真实 Markdown H1-H6 级别 |
| PDF 坐标 | Chunker 依赖 Canvas 恢复 | Chunker 不依赖 PDF/Canvas |
| 输出 | `list[dict]` | `list[DocumentChunk]` |
| 运行时 | `ProcessBase`、callback、DAG output | 普通同步 `.chunk(document)` |

## 13. 处理示例

输入 blocks：

```text
H1 子宫内膜癌诊疗指南
正文：一段概述
H2 诊断
正文：诊断内容 A
正文：诊断内容 B
H2 治疗
正文：治疗内容
```

`GroupTitleChunker(target_level=2)`：

```text
Chunk 1: 子宫内膜癌诊疗指南 + 一段概述
Chunk 2: 诊断 + 诊断内容 A + 诊断内容 B
Chunk 3: 治疗 + 治疗内容
```

`HierarchyTitleChunker(target_level=2)`：

```text
Chunk 1:
子宫内膜癌诊疗指南
一段概述

Chunk 2:
子宫内膜癌诊疗指南
诊断
诊断内容 A
诊断内容 B

Chunk 3:
子宫内膜癌诊疗指南
治疗
治疗内容
```

如果某个节点超过 `chunk_token_size`，标题路径会重复写入该节点拆出的每个正文 chunk。

## 14. 异常与退化规则

- 空文档返回空列表；
- 无标题文档由 Group/Hierarchy 退化为根 section 的固定 token 切分；
- 空标题文本不创建树节点；
- 缺少 `heading_level` 的 title 暂按一级标题处理；
- table/image 空文本仍保留还是丢弃，需要与 Parser 的空块规则统一，首版建议丢弃；
- Chunker 不吞掉取消或运行时异常；
- Chunker 不因某种策略失败而自动切换到另一种策略。

## 15. 测试要求

至少覆盖：

1. 中文文本按固定 token 大小切分且可无损拼回；
2. 本地没有 `cl100k_base` 缓存时不联网；
3. chunk 只带实际覆盖 block 的来源信息；
4. 重复页码被压缩成唯一 `pages`；
5. page marker 不进入标题树；
6. Group 不跨 `target_level` section；
7. Group 的超长 section 能继续按 token 切分；
8. Hierarchy 保留完整 `heading_path`；
9. Hierarchy 不丢失父节点直属正文；
10. Hierarchy 保留只有标题、没有正文的节点；
11. table/image 保持原子且继承当前标题路径；
12. 无标题文档稳定退化为 token 切分；
13. 空输入返回空列表；
14. 非法 method、`target_level` 和 `chunk_token_size` 明确报错。
15. outline depth 0/1/2 正确转换成 heading level 1/2/3；
16. 同级 outline 节点保持平级；
17. Plain JSON 顶层为 list，每个非空文本行固定包含五个字段；
18. 无 position 时 outline 在整份行列表中匹配，并且每个候选只消费一次；
19. 空 outline 或零命中时保留原 ParsedDocument；
20. Group 和 Hierarchy 都通过 TitleChunker 门面复用同一个 resolver。

## 16. 建议实施顺序

1. 先固定 `DocumentBlock -> DocumentChunk` 输入输出和 metadata 规则。
2. 完成 `common.py` 的 token、文本归一化、来源页码去重。
3. 完成纯固定步长 `TokenChunker`。
4. 完成 Group section 边界和 section 内切分。
5. 完成 Hierarchy 构树、标题路径和父节点直属正文。
6. 使用真实中文 PDF、Markdown、DOCX、表格样例保存每一步结果。
7. 用真实 PDF 验证自带 outline 能生成 heading path。
8. 最后再决定是否增加正则/layout 标题推断、overlap、delimiter 和 media context。

## 17. 待评审项

需要先确认以下三点，再继续改实现：

1. Hierarchy 的标题路径是否同时写入 chunk 正文和 metadata，还是只写 metadata；
2. 是否需要为没有 outline 的 Plain PDF 增加正则/layout 标题推断；
3. 来源信息是否采用本文建议的 `pages`，替换重复的 `block_metadata` 页码列表；
4. outline 标题模糊匹配阈值是否长期固定为 0.8。
