# File Parser 开发规范

## 1. 定位

`src/knowledge/file_parser/` 保存具体文件格式到 Markdown 的转换实现。每种格式独立一个
模块，不把多个格式的解析算法合并进 Flow 的统一入口。

File Parser 只负责：

1. 读取本地文件。
2. 校验自身格式参数。
3. 调用该格式所需的解析引擎。
4. 原生支持 Markdown 时提供 `to_markdown(...)`。
5. 不具备原生 Markdown 输出能力时，通过 `parse(as_json=True)` 输出自身定义的中间态。

它不负责 Chunk、向量化、数据库、对象存储或任务队列。

## 2. 当前目录

```text
src/knowledge/file_parser/
├── __init__.py
├── doc_parser.py
├── docx_parser.py
├── html_parser.py
├── image_parser.py
├── markdown_parser.py
├── pdf_parser.py
├── pptx_parser.py
├── table_parser.py
└── text_parser.py
```

本目录不包含 `registry.py` 或 `service.py`。文件类型路由只存在于
`src/knowledge/flow/parser/parser.py`。

## 3. 当前 Parser

| 文件类型 | Flow 实例内部 method | Parser / 引擎 | 交给 Flow 的结果 |
| --- | --- | --- | --- |
| PDF | `plain` | `PlainPdfParser` / pypdf | JSON 页面中间态 |
| PDF | `ocr` | `OcrPdfParser` / PaddleOCR | Markdown |
| DOCX | `python-docx` | `DocxParser` / python-docx | Markdown |
| DOCX | `docling` | `DoclingDocxParser` / Docling | Markdown |
| 图片 | `rapidocr` | `ImageParser` / RapidOCR | JSON OCR 中间态 |
| 图片 | `paddleocr` | `ImageParser` / PaddleOCR | JSON OCR 中间态 |
| 图片 | `unlimitedocr` | `ImageParser` / UnlimitedOCR | JSON OCR 中间态 |
| DOC | 不配置 | `DocParser` / Apache Tika | JSON HTML/文本中间态 |
| Markdown | 不配置 | `MarkdownParser` / Python-Markdown | 原 Markdown |
| TXT | 不配置 | `TextParser` / Python 文本读取 | JSON 文本中间态 |
| CSV、XLSX | 不配置 | `TableParser` / pandas、openpyxl | Markdown 表格 |
| PPTX | 不配置 | `PptxParser` / python-pptx | JSON 幻灯片中间态 |
| HTML | 不配置 | `HtmlParser` / BeautifulSoup、markdownify | Markdown |

`flow.Parser.__init__` 直接在 `flow/parser/parser.py` 内创建每个实例独立的 suffix
配置字典。`_pdf`、`_docx`、`_image` 等格式方法只读取这份实例内部配置。

调用方唯一可选的是构造 `Parser(parser_method="plain")` 或
`Parser(parser_method="ocr")`，用于确定 PDF 走普通解析还是 OCR。DOCX 和图片的
`parser_method` 由 `Parser.__init__` 的内部配置字典固定；`encoding`、`language`
等参数也全部由该字典提供。调用方不能通过 `DocumentFlow.parse_document(...)` 或
`run(...)` 逐次传入这些参数。

具体 File Parser 不接收、不判断 `parser_method`，每个 Parser 类只实现一种策略；
失败后不切换实现。方法选择只发生在 Flow 的 `_pdf`、`_docx`、`_image` 中。

## 4. 输出约定

具体 Parser 原生具备 Markdown 输出能力时，Flow 调用：

```python
markdown = await parser.to_markdown(path)
```

不具备原生 Markdown 输出能力时，Flow 调用：

```python
lines, outlines = await parser(path)
```

各 Parser 的 JSON schema 是内部中间态，不规定全局结构。唯一统一入口
`flow/parser/parser.py` 负责把该格式的中间态转成 Markdown，再通过
`MarkdownParser.parse_text(...)` 生成 blocks。

`Parser` 不提供统一 `parse(...)`。`DocumentFlow.parse_document(...)` 接收
`file_source` 和必传的 `file_name`，只从 `file_name` 取得 suffix 后调用
`_pdf/_doc/_docx/...`，不再接收独立 suffix 参数。每个格式方法直接接受
`str | Path | bytes | BinaryIO` file_source 和 `file_name`，不接收 `config`、
`options`、`encoding` 或 `language`；只有底层库要求 Path 时，当前格式方法才在内部
临时落盘。格式方法需要的参数由 `Parser.__init__` 初始化好的实例内部配置提供。

## 5. PDF 约定

PDF Flow 只保留两个互斥入口：

```text
Parser(parser_method="plain") -> PlainPdfParser -> 用 pypdf 只读 PDF 原生文本层，不提取图片
Parser(parser_method="ocr")   -> OcrPdfParser   -> 只调用 PaddleOCR
```

- Plain PDF 的包名和导入模块统一为全小写 `pypdf`，标准导入为
  `from pypdf import PdfReader`。不得使用旧包 `PyPDF2` 或更早的 `pyPdf`。
- Plain PDF 的行级 JSON list 保留在 `ParsedDocument.json_result`，原路径或 bytes
  保留在 `ParsedDocument.file_source`，供 TitleChunker 调用
  `extract_pdf_outline(...)`。
  这两个字段不得塞入会复制到每个 chunk 的 metadata。
- Plain PDF 的每个非空文本行固定输出五个字段：

  ```json
  {
    "text": "文本内容",
    "layout_type": "",
    "doc_type_kwd": "text",
    "position": [],
    "image": null
  }
  ```

  JSON 顶层必须是 list，不增加额外外壳。Plain 只读取文本层，因此除了 `text`
  和固定为 `"text"` 的 `doc_type_kwd`，其余字段保持空值。
- 具体路径成功后直接返回自己的结果。
- 任一路径失败都直接抛出 `PdfParseError`。
- OCR 失败不得改用 Plain，两种实现之间不存在 fallback。
- OCR 结果没有真实页码时不得伪造页码。
- 取消异常不得转成普通失败。
- 不保留负责再次判断 `parser_method` 的 `PdfParser` 兼容门面。
- PDF Flow 不提供 Docling 用户分支，构造参数也不接受 `docling`。

## 6. DOCX 约定

DOCX 精确支持两种实现：

```text
python-docx -> DocxParser.to_markdown(...)
docling     -> DoclingDocxParser.to_markdown(...)
```

`_docx` 只读取 `Parser.__init__` 创建的实例内部配置字典并实例化对应类，不接受调用
方传入的 method 或 options。两个具体 Parser 都不接收 `parser_method`，也互不兜底；
`DocxParser` 解析失败或返回空结果时直接抛错，不再自动调用
`DoclingDocxParser`。

## 7. Markdown Parser

`MarkdownParser` 同时提供：

```python
parse(filename, ...)
parse_text(text, ...)
```

`parse()` 读取文件后复用 `parse_text()`。`parse_text(as_json=True)` 返回 Markdown
渲染结果和顺序化 elements，供 Flow 投影标题、正文和表格 blocks。

## 8. OCR 边界

PDF 和图片 Parser 可以 import `src.knowledge.flow.extractor`，但不能复制 OCR HTTP、
轮询或本地模型实现。

- `Parser(parser_method="ocr")` 使 PDF 进入 `OcrPdfParser`，其 provider 固定为
  PaddleOCR。
- 图片的 `parser_method` 由 Flow 实例内部配置映射到 `rapidocr`、`paddleocr` 或
  `unlimitedocr`，只调用内部配置指定的 provider；用户不能逐次选择。
- OCR 返回空内容视为失败。
- OCR 凭据缺失必须报告明确配置项。

## 9. 新格式接入

增加格式时：

1. 新增独立的 `<format>_parser.py`。
2. 原生支持 Markdown 时提供 `to_markdown(...)`；否则定义清晰的 JSON 中间态。
3. 在 `flow/parser/parser.py` import 该类并增加唯一 suffix 映射及格式方法。
4. 在 `test/` 增加 Markdown、参数、空结果和失败测试。

不要新增第二个 registry，也不要把具体解析代码写进 Flow Parser。
