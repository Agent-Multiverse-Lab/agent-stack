# Knowledge Flow 设计

> 状态：首版实现

## 1. 处理链路

所有支持的文件都由 `DocumentFlow` 根据 `file_name` 的 suffix 选择 `Parser`
格式方法，再由该方法调用 `src/knowledge/file_parser/` 中的具体 File Parser：

```text
file_source（str / Path / bytes / BinaryIO）+ file_name
  -> Parser.__init__(...) 初始化实例内部配置
  -> DocumentFlow.parse_document(...) 按 suffix 分发
  -> Parser._pdf/_doc/_docx/...(file_source)
  -> 仅在底层库要求 Path 时由当前格式方法临时落盘
  -> Markdown 中间结果
  -> Markdown Blocks
  -> Chunker
  -> DocumentChunk
```

默认链路为：

```text
Parser -> TitleChunker(method="hierarchy")
```

调用方仍可显式选择 Token Chunker 或 Group Title Chunker。Flow 不做向量化、数据库、
对象存储、队列或知识库写入。

## 2. 目录边界

```text
src/knowledge/
├── file_parser/
│   ├── __init__.py
│   ├── doc_parser.py
│   ├── docx_parser.py
│   ├── html_parser.py
│   ├── image_parser.py
│   ├── markdown_parser.py
│   ├── pdf_parser.py
│   ├── pptx_parser.py
│   ├── table_parser.py
│   └── text_parser.py
├── flow/
│   ├── __init__.py
│   ├── pipeline.py
│   ├── types.py
│   ├── parser/
│   │   ├── __init__.py
│   │   └── parser.py
│   ├── extractor/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── extractor.py
│   │   ├── paddle_ocr.py
│   │   ├── rapid_ocr.py
│   │   └── unlimited_ocr.py
│   └── chunker/
│       ├── __init__.py
│       ├── common.py
│       ├── token_chunker.py
│       └── title_chunker/
│           ├── __init__.py
│           ├── title_chunker.py
│           ├── group_chunker.py
│           └── hierarchy_chunker.py
└── spec/
    └── flow_develop_spec.md
```

职责边界：

- `file_parser/` 保存各文件格式的具体读取与解析实现。
- `flow/parser/parser.py` 保存各格式方法及唯一一份 suffix 分发表。
- `DocumentFlow` 接收 `file_source` 和 `file_name`，从 `file_name` 取得 suffix 后调用
  对应格式方法；不再接收单独的 suffix 参数。
- 每个 `_pdf/_doc/...` 都直接接受 `str | Path | bytes | BinaryIO`；只有底层库确实
  要求路径时，当前格式方法才在内部临时落盘。
- `Parser._document(...)` 只负责 Markdown 归一化和 blocks 投影，不负责格式分发。
- `flow/extractor/` 只负责 OCR 能力，不决定文件格式、File Parser 或 Chunker。
- `flow/chunker/` 只消费 `ParsedDocument.blocks`。
- `pipeline.py` 只编排 Parser 和 Chunker。

`file_parser/` 不设置格式注册表或服务层。具体 File Parser 也不决定后续使用哪一种
Chunker。

## 3. Parser 格式方法

### 3.1 公开入口

公开文件入口是 `DocumentFlow.parse_document(file_source, file_name=...)`。`Parser`
不再提供统一 `parse(...)` 方法。

`Parser` 至少提供以下方法：

```python
class Parser:
    def __init__(
        self,
        *,
        parser_method: Literal["plain", "ocr"] = "plain",
    ): ...

    async def _pdf(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _doc(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _docx(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _markdown(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _text(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _table(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _pptx(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _html(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
    async def _image(file_source: str | Path | bytes | BinaryIO, *, file_name: str): ...
```

`Parser.__init__` 直接在 `flow/parser/parser.py` 内创建按 suffix 索引的配置字典。
每个 `Parser` 实例都独立初始化一份，其他格式方法只读取这份实例字典。

公开配置入口只有构造时的 `parser_method`，且只表示 PDF 使用普通解析还是 OCR：

```python
plain_parser = Parser(parser_method="plain")
ocr_parser = Parser(parser_method="ocr")
```

省略 `parser_method` 时使用 `Parser.__init__` 内定义的 PDF 默认值 `plain`。调用方
不能在 `DocumentFlow.parse_document(...)` 或 `run(...)` 中传入 `parser_method`、
`encoding`、`language` 或其他格式 option。DOCX、图片、文本、表格等格式的解析引擎
和参数都由 `__init__` 的内部配置字典固定。

`DocumentFlow` 只从必传 `file_name` 取得 suffix 并找到对应 `_pdf/_doc/...`。
`file_source` 是路径、bytes 还是字节流都不影响格式判断；不根据 MIME、正文内容或
解析结果猜测格式，也不再提供额外 suffix 参数。

### 3.2 suffix 分发表

| suffix | `Parser` 格式方法 |
| --- | --- |
| `.pdf` | `_pdf` |
| `.doc` | `_doc` |
| `.docx` | `_docx` |
| `.md`、`.markdown` | `_markdown` |
| `.txt` | `_text` |
| `.csv`、`.xlsx` | `_table` |
| `.pptx` | `_pptx` |
| `.html`、`.htm` | `_html` |
| `.png`、`.jpg`、`.jpeg`、`.webp`、`.bmp`、`.gif`、`.tif`、`.tiff` | `_image` |

路由规则：

1. suffix 只从 `file_name` 读取，统一转为小写并保留前导点。
2. `file_name` 必传并且必须带后缀。
3. `.csv` 和 `.xlsx` 进入同一个 `_table` 方法。
4. `.xls`、`.ppt`、`.json` 等未列出的格式直接报错。
5. 格式专属参数只从 `Parser` 实例内部配置读取，并由对应格式方法消费；调用方不能
   逐次传入。
6. suffix 只选择格式方法，不选择 Chunker。

## 4. 格式方法与 File Parser

每个格式方法负责：

1. 从 `Parser` 实例内部映射读取该 suffix 的配置。
2. 仅在该格式内部配置了多个实现时，读取内部 `parser_method` 并精确选择实现。
3. 校验并传递该格式专属参数。
4. 取得 Markdown，或取得 JSON 中间态后在 `parser.py` 转成 Markdown。
5. 返回实际 Parser 及必要 metadata，供公共收尾逻辑记录来源。

具体关系如下：

| 格式方法 | 实例内部 method | 具体 File Parser / 引擎 | Markdown 取得方式 |
| --- | --- | --- | --- |
| `_pdf` | `plain` | `PlainPdfParser` / pypdf | 逐页调用 `page.extract_text()` 读取原生文本层并提取大纲，只返回原始行列表和大纲；行级 JSON 字段及 Markdown 均由 `parser.py` 组装 |
| `_pdf` | `ocr` | `OcrPdfParser` / PaddleOCR | 直接调用 `to_markdown(...)` |
| `_doc` | 不配置 | `DocParser` / Apache Tika | `parse(as_json=True)` 后由 `parser.py` 将 HTML/文本转 Markdown |
| `_docx` | `python-docx` | `DocxParser` / python-docx | 直接调用 `to_markdown(...)` |
| `_docx` | `docling` | `DoclingDocxParser` / Docling | 直接调用 `to_markdown(...)` |
| `_markdown` | 不配置 | `MarkdownParser` | 直接调用 `to_markdown(...)` |
| `_text` | 不配置 | `TextParser` | `parse(as_json=True)` 后由 `parser.py` 取得文本 |
| `_table` | 不配置 | `TableParser` | 直接调用 `to_markdown(...)` |
| `_pptx` | 不配置 | `PptxParser` | `parse(as_json=True)` 后由 `parser.py` 按幻灯片结构转 Markdown |
| `_html` | 不配置 | `HtmlParser` | 直接调用 `to_markdown(...)` |
| `_image` | `rapidocr` | `ImageParser` / RapidOCR | `parse(as_json=True, extractor_type="rapidocr")` 后由 `parser.py` 将 OCR lines 转 Markdown |
| `_image` | `paddleocr` | `ImageParser` / PaddleOCR | `parse(as_json=True, extractor_type="paddleocr")` 后由 `parser.py` 将 OCR lines 转 Markdown |
| `_image` | `unlimitedocr` | `ImageParser` / UnlimitedOCR | `parse(as_json=True, extractor_type="unlimitedocr")` 后由 `parser.py` 将 OCR lines 转 Markdown |

规则：

- 具体 File Parser 原生支持 `to_markdown(...)` 时直接调用，不重复实现转换。
- 没有 `to_markdown(...)` 时，Flow 请求该 Parser 自己定义的 JSON 中间态，并只在
  `parser.py` 中完成该格式到 Markdown 的适配。
- 各格式 JSON schema 互不相同，只是内部中间态，不作为 Flow 公共返回值。
- Flow 不要求所有 File Parser 为统一接口而增加没有职责的空壳方法。
- File Parser 的读取、解析引擎调用和格式校验仍留在各自模块，不能复制进
  `parser.py`。
- `parser_method` 的判断只存在于 `flow/parser/parser.py` 的 `_pdf`、`_docx`、
  `_image` 等格式方法中。具体 File Parser 不接收、不判断 `parser_method`，每个类
  只实现一种解析策略。
- PDF Flow 不保留用于二次分发的 `PdfParser` 门面，也不提供 Docling 用户分支；只在
  `PlainPdfParser` 和 `OcrPdfParser` 两个单策略类之间选择。
- DOCX 的 python-docx 与 Docling 分别由 `DocxParser` 和 `DoclingDocxParser` 实现，
  两个类之间不调用、不兜底。具体使用哪一个由 `Parser.__init__` 的内部配置字典
  固定，不是用户参数。
- 图片 OCR 引擎同样由 `Parser.__init__` 的内部配置字典固定，不作为构造参数或调用
  参数暴露。
- DOC、Markdown、TXT、表格、PPTX 和 HTML 当前都只有一种处理方式，不设置
  `parser_method`。

## 5. 内部配置与唯一外部选择

所有格式配置都直接定义并初始化在 `Parser.__init__` 的实例字典中，此后所有格式
方法只读取该实例内部配置。

```python
plain_flow = DocumentFlow(parser=Parser(parser_method="plain"))
ocr_flow = DocumentFlow(parser=Parser(parser_method="ocr"))
```

调用方需要在普通 PDF 与 OCR PDF 之间选择时，应先构造对应 `Parser`，再注入
`DocumentFlow`。`DocumentFlow.parse_document(...)` 和 `run(...)` 都不接受调用级
解析配置。

外部允许值固定为：

| 构造参数 | PDF 路径 |
| --- | --- |
| 省略或 `plain` | `PlainPdfParser` |
| `ocr` | `OcrPdfParser` |

其他设置全部是内部实现配置：

| 格式 | 内部配置 |
| --- | --- |
| DOCX | `parser_method` 由 `Parser.__init__` 的内部字典固定，格式方法据此选择 `python-docx` 或 `docling` |
| 图片 | `parser_method` 由 `Parser.__init__` 的内部字典固定，格式方法据此选择内部 OCR 引擎 |
| TXT、CSV、HTML 等 | `encoding` 等参数由 `Parser.__init__` 的内部字典固定 |
| PDF OCR 与图片 | `language` 等 OCR 参数由 `Parser.__init__` 的内部字典固定 |

这些内部值不进入 `DocumentFlow.parse_document(...)` 或 `run(...)` 的公开参数。
格式方法内部不增加额外的方法选择函数，也不遍历、探测或自动切换实现。选中的实现
报错、超时、返回空结果或被取消时，异常直接向上传播。

## 6. PDF 处理方式

PDF 只允许精确选择一条路径：

```text
Parser(parser_method="plain") -> PlainPdfParser
Parser(parser_method="ocr")   -> OcrPdfParser
```

约束：

- 默认选择 Plain。
- Plain PDF 的依赖和导入模块统一使用当前维护的全小写 `pypdf`：

  ```python
  from pypdf import PdfReader
  ```

  不得安装或导入旧包 `PyPDF2`，也不得使用更早的 `pyPdf`。
- Plain 路径不构造、不探测、不调用任何 OCR Extractor。
- OCR 路径只构造并调用 `OcrPdfParser`，当前固定使用 PaddleOCR。
- OCR 成功后直接使用 OCR Markdown。
- 任一路径配置缺失、服务不可用、超时、失败或空结果时原样抛错。
- OCR 失败不得调用 `PlainPdfParser`，两种路径之间没有自动兜底。
- PDF Flow 不接受 `docling`，也不把 Docling 暴露为用户选择。
- `CancelledError` 必须直接向上传播。

Plain 路径在 JSON 中间态中为每个非空文本行生成一个对象，顶层直接使用 list：

```json
{
  "text": "文本内容",
  "layout_type": "",
  "doc_type_kwd": "text",
  "position": [],
  "image": null
}
```

Plain JSON 顶层就是 list，不增加额外外壳。除了 `text` 和固定为 `"text"` 的
`doc_type_kwd`，其他字段保持空值。

OCR 结果只有在服务返回真实页边界时才记录页码；没有真实页码时不得制造
`page: 1` 等假来源。

## 7. Markdown 中间层

每个格式方法最终都返回 Markdown。公共收尾逻辑：

```text
格式方法返回 Markdown
  -> 统一 CRLF/CR 为 LF
  -> 保存到 ParsedDocument.markdown
  -> MarkdownParser.parse_text(as_json=True)
  -> list[DocumentBlock]
```

这一过程直接写在 `parser.py` 的私有辅助函数中，不再拆出额外的 Flow Parser 层。

`ParsedDocument` 保存：

```text
ParsedDocument
├── name
├── suffix
├── markdown
├── blocks
├── metadata
├── json_result
└── file_source
```

其中：

- `markdown` 是可检查、可保存的中间产物。
- `blocks` 是供 Chunker 使用的语义投影，不能用于反向重建 Markdown。
- Plain PDF 的 `json_result` 保存 Parser 已读取的行级 JSON list，`file_source` 保存
  路径或原始 bytes，供 TitleChunker 调用 PDF outline 解析；二者不放入 metadata。
- 标题保留 `heading_level`。
- 表格保留为原子 `table` block。
- 图片 OCR 正文保留为 `image` block。
- 只有表头、没有数据行的 Markdown 表格仍必须保留。
- Plain PDF 不制造页面标记或默认页码。

## 8. Extractor 边界

- `flow/extractor/` 只实现 OCR provider、状态检查和 OCR 结果。
- `_pdf` 和 `_image` 只通过对应 File Parser 间接使用 Extractor。
- Extractor 不读取 Flow suffix 分发表，不选择 File Parser，不生成 chunks。
- `Parser(parser_method="ocr")` 的 PDF 路径固定选择 PaddleOCR，不执行 provider
  级兜底。
- 图片 OCR provider 由 `Parser.__init__` 的内部配置字典固定，不由调用方逐次选择，
  也不调用其他 provider。
- OCR 返回空内容视为失败。

## 9. Chunker

### 9.1 Token Chunker

- 按固定 token 步长连续切分。
- 首版没有 overlap 和分隔符优先。
- 表格和图片保持原子块。
- 每个 Chunk 的 `block_metadata` 只包含自身实际覆盖的来源 blocks。

### 9.2 Group Title Chunker

- TitleChunker 先调用 `chunker/common.py::resolve_outline_levels(document)`。该函数
  使用 `extract_pdf_outline(document.file_source)`，读取 Plain PDF 行级 JSON list，
  并补充 `title + heading_level`。
- 按目标标题层级划分 section。
- 同一 section 的连续段落尽量合并。
- 严格不跨目标标题边界。
- 表格和图片打断正文合并，但仍归属当前 section。
- 超长 section 复用 Token Chunker。

### 9.3 Hierarchy Title Chunker

- 与 Group 共用同一个 `resolve_outline_levels`，不在具体策略内重复解析 outline。
- 按标题级别建立层级。
- 完整 `heading_path` 保存在 metadata。
- 父标题直属正文不能丢失。
- 超长节点复用来源感知的 Token Chunker。
- 无标题文档按根 section 处理。

## 10. Pipeline 默认值

```python
flow = DocumentFlow(parser=Parser(parser_method="plain"))
await flow.run(
    file_source,
    file_name="document.pdf",
    chunker="title",
    title_method="hierarchy",
    target_level=3,
    chunk_token_size=512,
)
```

`DocumentFlow` 通过构造器注入 `Parser`。需要 OCR PDF 时注入
`Parser(parser_method="ocr")`；`run(...)` 本身不加载、不接收逐次解析参数。
Pipeline 根据 `file_name` 查 suffix 映射并选择对应 Parser 格式方法，但不直接选择
具体 File Parser 或 OCR provider，也不吞掉 Parser、Extractor 或 Chunker 异常。

## 11. 旧目录删除与规范迁移清单

迁移完成后只保留新 Flow 和 `file_parser/` 具体实现：

1. 更新所有测试和调用方，统一使用 `src.knowledge.flow.Parser` 或
   `src.knowledge.flow.DocumentFlow`。
2. 更新 `src/knowledge/__init__.py`，解除对旧 Chunk 包的强制导入，同时保留知识库本身
   的 `BaseKnowledge`、`KnowledgeRecord`、`KnowledgeSearch`、`KnowledgeFactory` 和
   `KnowledgeType` 导出。
3. 确认新 `file_parser/` 和 Flow Parser 不再 import 旧 Parser/Extractor/Chunk 路径。
4. 删除旧 `src/knowledge/parser/` 中的多 Parser 导出、注册表、服务和旧格式实现。
5. 删除旧 `src/knowledge/extractor/`；OCR 实现只保留在 `src/knowledge/flow/extractor/`。
6. 删除旧 `src/knowledge/chunk/`；Token、Group、Hierarchy 只保留新实现。
7. 删除无源码职责的 `src/knowledge/cleaner/` 残留。
8. 删除或迁移旧 Parser/Chunk 规范，避免出现第二套目录、路由或 profile 说明。
9. 若不保留旧文本聚类工具，移除其唯一直接依赖 `scikit-learn` 并更新 lock。
10. 最后重新搜索旧 import，执行根包、API、worker、SearchAgent 和 Flow 的 import
    smoke。

旧 import 如需短期兼容，只允许转发到新入口，不得复制解析或分块算法。兼容期结束后
删除转发。

## 12. 必需测试

- `DocumentFlow.parse_document` 对每个受支持 suffix 只调用对应格式方法。
- 每个格式方法都直接接受 `str`、`Path`、`bytes` 或 `BinaryIO` file_source。
- `file_name` 无 suffix 或 suffix 不支持时明确失败。
- 不提供独立 suffix 参数；格式只由 `file_name` 决定。
- 每个格式方法只调用表格中指定的具体 File Parser。
- 原生 `to_markdown` 路径不请求 JSON 中间态。
- JSON 中间态路径能在 `parser.py` 生成稳定 Markdown。
- `Parser.__init__` 为不同实例分别创建内部配置字典，实例之间互不影响。
- `Parser(parser_method="plain")` 与 `Parser(parser_method="ocr")` 分别只进入对应
  PDF 路径，其他值直接报错。
- `DocumentFlow.parse_document(...)` 和 `run(...)` 不接受 `parser_method`、
  `encoding`、`language` 等逐次解析参数。
- PDF Plain 不构造 OCR；PDF OCR 失败不调用 Plain；PDF Flow 不提供 Docling 分支。
- DOCX 的 `python-docx` 与 `docling` 路径互不兜底，并且只能由内部配置选择。
- 图片只调用内部配置指定的一个 OCR provider。
- Parser、Extractor 的失败和 `CancelledError` 原样传播。
- Markdown 标题、正文、链接、表格、表头空表和 PDF 页码来源能生成正确 blocks。
- Token、Group、Hierarchy 满足第 9 节规则。
- `DocumentFlow` 端到端只执行一次 Parser，并使用调用方显式选择的 Chunker。

测试和样例统一放在仓库 `test/` 下。OCR 在线调用不可用时必须记录明确失败，已有 OCR
Markdown 只能标记为回放结果，不能冒充本次在线 OCR 成功。
