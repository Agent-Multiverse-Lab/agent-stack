# Parser 引擎参考（已废弃）

> **状态：已废弃，仅保留历史讨论，不代表当前实现或当前设计。**
>
> 当前唯一有效规范是
> [`flow_develop_spec.md`](./flow_develop_spec.md)。本文后续出现的旧目录、registry、
> MIME 路由、`enable_ocr`、优先级列表和自动 fallback 等内容均已失效，不得作为实现
> 依据。

> `ExcelParser` 的引擎基线已迁入统一 Parser；不恢复独立 `TableParser`。

## 1. 目标

在 `src/knowledge/parser/` 下按文档领域拆分 parser。每个文档领域只有一个对外暴露并
注册的 Parser 类，例如 `PdfParser`、`DocxParser`、`ExcelParser`、`PptxParser`。
同一领域可以包含多个相关文件格式：CSV 和 XLSX 都属于 Excel 领域，只由
`ExcelParser` 处理。统一注册表只负责把扩展名、MIME 和显式类型路由到对应 Parser；
同一领域需要多个格式读取器或解析引擎时，由该 Parser 在内部选择。

Parser 的核心职责只有：

1. 从本地 `filename` 或二进制 `byte_stream` 读取内容，并校验该类型特有的参数。
2. 按请求将文件内容输出为 Markdown 或 JSON；未指定时默认 Markdown。

格式 parser 不负责文本清洗、分块、向量化、数据库、对象存储或任务队列。
现有 `src/knowledge/chunk/` 仍只接收规范化后的 Markdown；调用方按具体 Parser 的
返回结构取得 Markdown 后再交给分块，不在这里规定统一字段路径。
表格是 PDF、DOCX、PPTX、HTML 等文档格式内部的一种内容结构，应由对应 Parser
提取和输出，不能恢复一个跨格式的 `TableParser`。`ExcelParser` 的职责是解析 CSV
和 XLSX 电子表格文件，不是替其他文档 Parser 解析内嵌表格。
PDF 和图片的 OCR 引擎继续复用 `src/knowledge/extractor/`，不在新目录中复制
PaddleOCR/RapidOCR 的 HTTP 或模型调用代码。

## 2. 本文采用的优先级解释

PDF 使用一个对外的 `PdfParser` 编排内部实现，`enable_ocr` 决定入口：

```text
enable_ocr=false -> PlainPdfParser（pdfreader）
enable_ocr=true  -> OcrPdfParser（PaddleOCR） -> PlainPdfParser（pdfreader 兜底）
```

DOCX 的顺序为：

```text
DOCX: python-docx（首选） -> Docling（兜底）
```

`PlainPdfParser` 是 PDF 的非 OCR 实现，也是 OCR 路径失败后的唯一兜底。
`BasePdfParser`、`PlainPdfParser` 和 `OcrPdfParser` 都是 `pdf_parser.py` 的内部实现，不进入
全局注册表。兜底是 `PdfParser` 内部的顺序尝试，不同时运行，也不合并两份结果。

## 3. 文档领域与文件类型路由

| 文档领域 | Parser | 扩展名 / MIME | Parser 内部引擎顺序 | 可选输出 |
| --- | --- | --- | --- | --- |
| PDF | `PdfParser` | `.pdf` / `application/pdf` | OCR 关闭：pdfreader；OCR 开启：PaddleOCR -> pdfreader | Markdown / JSON |
| DOCX | `DocxParser` | `.docx` / `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx -> Docling | Markdown / JSON |
| DOC | `DocParser` | `.doc` / `application/msword` | Apache Tika | Markdown / JSON |
| Markdown | `MarkdownParser` | `.md`、`.markdown` / `text/markdown` | Python-Markdown | Markdown / JSON |
| TXT | `TextParser` | `.txt` / `text/plain` | Python 文本读取 | Markdown / JSON |
| Excel（CSV / XLSX） | `ExcelParser` | `.csv`、`.xlsx` / `text/csv`、`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | CSV：pandas.read_csv；XLSX：pandas.read_excel + openpyxl | Markdown / JSON |
| PPTX（PowerPoint） | `PptxParser` | `.pptx` / `application/vnd.openxmlformats-officedocument.presentationml.presentation` | python-pptx | Markdown / JSON |
| 图片 | `ImageParser` | `.png`、`.jpg`、`.jpeg`、`.webp`、`.bmp`、`.gif`、`.tif`、`.tiff` / `image/*` | RapidOCR -> PaddleOCR -> UnlimitedOCR | Markdown / JSON |
| HTML | `HtmlParser` | `.html`、`.htm` / `text/html`、`application/xhtml+xml` | BeautifulSoup + markdownify | Markdown / JSON |

所有 Parser 的默认输出模式都是 Markdown。只有调用方通过具体 Parser 自己定义的参数
显式选择 JSON 时才产生 JSON。JSON 是输出格式，不代表首期支持把 `.json` 文件作为
输入。

这里的“直接读取”表示不经过 Docling、OCR 或通用文档转换器。`ExcelParser` 对 CSV
使用 `pandas.read_csv`，对二进制 XLSX 容器使用
`pandas.read_excel`，并依赖 openpyxl 读取；二者共用一个 Parser 入口和输出模型，
但不混淆底层文件格式。

`python-pptx` 只负责 PowerPoint 2007 及之后的 `.pptx`。旧二进制 `.ppt` 不能直接
交给 `python-pptx`，首期不支持；后续若需要，应先明确 LibreOffice 转换或 Tika
解析链。

首期不处理未列出的 `.xls`、`.ppt`、`.json` 等格式。`.xls` 即使属于 Excel 领域，
在明确读取引擎和测试样例前也不能仅凭 `ExcelParser` 的名称获得隐式支持。

## 4. 建议目录结构

每个文档领域直接使用一个 `xx_parser.py`，不再为单个领域套同名子目录：

```text
src/knowledge/parser/
├── __init__.py
├── registry.py
├── service.py
├── parser_develop_spec.md
├── pdf_parser.py
├── docx_parser.py
├── doc_parser.py
├── markdown_parser.py
├── text_parser.py
├── excel_parser.py
├── pptx_parser.py
├── image_parser.py
└── html_parser.py
```

每个模块只提供一个对外 Parser 类。`excel_parser.py` 只提供 `ExcelParser`，在类
内部区分 CSV 和 XLSX 读取方式，不拆成 `CsvParser`、`XlsxParser` 或
`TableParser`。根目录 `__init__.py` 只导出这些对外类，`registry.py` 也只注册
这些类。PDF 是首个允许模块内继承的特例：
`pdf_parser.py` 同时定义 `BasePdfParser`、`PlainPdfParser`、`OcrPdfParser` 和对外门面
`PdfParser`，但根目录 `__init__.py` 只导出 `PdfParser`。前三者不注册，也不能由
调用方绕过 `PdfParser` 直接选择。

首期不预建 helper 目录或多层 adapter；类型专属的输入、返回类型和内部 helper 先与
Parser 放在同一个 `xx_parser.py`。`BasePdfParser` 只复用 PDF 内部逻辑，不能上移成
所有文件类型的公共基类。共享流程放在 `service.py`，出现真实重复后再决定是否拆分。

## 5. 各 Parser 独立定义调用边界

首期不定义公共 `ParseRequest`、`ParserOutput` 或根目录 `types.py`。每个类型 Parser
在自己的 `xx_parser.py` 中定义参数、结果容器和解析异常。各 Parser 只共享输入载体
的范围：

- `filename`：本地文件名或路径。
- `byte_stream`：可读取的二进制流。

每个 Parser 自己决定支持其中一种还是两种，以及具体参数名、类型和流能力要求。
`byte_stream` 本身不携带可靠的文件类型；调用方必须另外提供文件名、MIME 提示或直接
指定 Parser，否则注册表拒绝猜测。

PDF 可以增加页码范围和 OCR 参数；`ExcelParser` 可以为 CSV 增加编码和分隔符参数，
为 XLSX 增加工作表选择参数，并根据实际输入格式校验哪些参数可用。不得为了制造统一
签名，把这些必需参数塞进
`options: Mapping[str, object]` 或无约束的 `**kwargs`。

各 Parser 可以继续使用 `parse(...)` 作为入口名称，但不要求方法签名、返回类型、
字段名或异常类型相同。`service.py` 只负责选择 Parser，不把具体结果改造成统一
Python 对象。

文本、Excel、HTML 等本地 Parser 没有独立服务状态；PaddleOCR 和 Tika 的可用性检查
属于对应 Parser 内部。任务取消异常必须继续向上传播，不能被当成普通引擎失败后触发
兜底。

### 5.1 输出格式

每个 Parser 都要具备两种输出能力：

- Markdown：默认模式，核心正文是 UTF-8 Markdown 文本。
- JSON：核心结果可被标准 JSON 编码器序列化。

未显式选择输出模式时使用 Markdown。具体模式参数叫什么、Markdown/JSON 如何包装、
JSON 使用哪些字段，都由对应 Parser 自己定义并测试。这里不规定公共 JSON schema，
也不要求所有 Parser 返回 Mapping 或同一种对象。内部引擎切换时不能静默改变调用方
选择的输出模式。

## 6. 注册与分发

`registry.py` 保存文件类型到 Parser 的显式映射，不通过目录扫描或类名猜测自动
注册。多个相关文件类型可以映射到同一个领域 Parser：

```text
pdf   -> PdfParser
docx  -> DocxParser
doc   -> DocParser
md    -> MarkdownParser
txt   -> TextParser
csv   -> ExcelParser
xlsx  -> ExcelParser
pptx  -> PptxParser
image -> ImageParser
html  -> HtmlParser
```

`csv` 和 `xlsx` 是两个文件类型路由键，但它们的值必须是同一个
`ExcelParser` 类。这样可以继续校验显式 `parser_type` 与扩展名/MIME 是否一致，
同时不会产生两个 Parser 实现。注册表中不能出现独立的 `CsvParser` 或
`XlsxParser`。

分发顺序：

1. 有 `filename` 时规范化扩展名；只有 `byte_stream` 时读取调用方提供的文件名、MIME
   或 Parser 类型提示。
2. 若调用方显式指定类型 Parser，从注册表按名称取得该 Parser，并验证输入类型与
   注册项一致。
3. 否则扩展名优先；扩展名缺失或未知时再使用 MIME。
4. 从注册表取出唯一的领域 Parser。
5. 调用方按照该 Parser 自己的签名传入 `filename` 或 `byte_stream` 及类型专属参数。
6. 类型 Parser 按自己的内部引擎顺序解析并处理兜底，结果按自身返回类型直接返回。

是否提供内部引擎选择参数、参数名称以及指定引擎后是否继续兜底，均由具体 Parser
定义。PDF 不对外暴露内部类名，调用方只使用它定义的 `enable_ocr` 参数，具体选择与
兜底由 `PdfParser` 决定。

不得把入参交给所有 Parser 逐个试错。文件类型路由和同类型 Parser 内部的引擎兜底是
两个独立步骤。

### 6.1 新增文档领域或相关格式

新增文档领域时固定执行四步：

1. 新建 `<type>_parser.py`，实现唯一对外的 `<Type>Parser`，并明确它接受
   `filename`、`byte_stream` 或两者。
2. 在根目录 `__init__.py` 导出该 Parser。
3. 在 `registry.py` 增加一条文件类型映射。
4. 增加该类型的路由、Markdown/JSON 输出和失败测试。

同一领域新增相关格式时，扩展现有领域 Parser 及其路由映射，不新建职责重叠的
Parser。`service.py` 不增加格式判断分支，其他领域 Parser 也不需要修改。

## 7. 成功与兜底原则

满足以下条件才视为成功：

- parser 正常完成；
- 按该 Parser 自己的约定产生调用方选择的 Markdown 或 JSON 内容；
- Markdown 核心正文是文本，JSON 核心结果可被标准 JSON 编码器序列化；
- 非空源文件得到非空的选定格式内容。

下列情况触发当前类型 Parser 的下一个内部兜底引擎：

- 依赖或外部服务不可用；
- 超时、连接失败或解析库抛出异常；
- parser 明确返回失败；
- 非空文件只得到空白内容；
- 输出无法规范化为调用方请求的 Markdown 或 JSON。

零字节的 Markdown/TXT/CSV 文件可以合法返回空内容；是否以及如何标记空源文件由对应
Parser 自己决定。PDF、DOCX、DOC、XLSX、图片等非空容器解析为空时不能伪装成成功。

是否返回引擎、兜底状态、attempts、耗时等信息，以及这些信息的字段名称，也由具体
Parser 决定，不建立公共元数据结构。

错误信息不得包含文件正文、API Key 或完整外部服务响应。

## 8. 各类型实现细则

### 8.1 PDF

- `PdfParser` 是 PDF 类型唯一对外暴露和注册的 Parser，负责选择实现、执行兜底并
  按自己的结果类型记录尝试信息；它不直接实现 pdfreader 或 OCR 提取。
- `BasePdfParser` 是 `pdf_parser.py` 内部基类，使用模板方法统一完成 PDF 请求校验、空结果
  判定以及 Markdown/JSON 规范化，并把具体内容提取和返回类型留给子类。
- `PlainPdfParser(BasePdfParser)` 使用 Python `pdfreader` 包按页面读取文本，不调用
  OCR。它既是 `enable_ocr=false` 时的直接实现，也是 OCR 路径失败时的兜底实现。
- `OcrPdfParser(BasePdfParser)` 复用现有 `PaddleOCRExtractor`，不复制 HTTP 或鉴权
  逻辑。
- `pdf_parser.py` 不得导入或调用 Docling；Docling 只保留给其他已明确使用它的文件
  类型。

内部关系固定为：

```text
BasePdfParser
├── PlainPdfParser  -> pdfreader（非 OCR）
└── OcrPdfParser    -> PaddleOCR

PdfParser
├── enable_ocr=false -> PlainPdfParser
└── enable_ocr=true  -> OcrPdfParser
                         └── 失败 -> PlainPdfParser
```

- `enable_ocr=false` 时不得探测或调用 PaddleOCR；直接调用 `PlainPdfParser`，且
  该路径不算兜底。
- `enable_ocr=true` 时先调用 `OcrPdfParser`；成功后不得再调用
  `PlainPdfParser`。PaddleOCR 未配置、不可用、超时、失败、返回空内容或无法规范化
  时，才调用 `PlainPdfParser`。
- `PlainPdfParser` 保持 PDF 页码和页顺序，提取到的文本按页转换为 Markdown 和
  自己定义的 JSON 结果。图片扫描件没有文本层时不得伪造成功。
- `PlainPdfParser.extract_outlines(filename)` 直接返回 pdfreader PDF Catalog 中的
  `Outlines`；目录提取是独立方法，不改变 `parse()` 的正文返回值。
- `PlainPdfParser` 失败后没有第三个 PDF 实现可继续尝试。OCR 开启路径汇总两次
  attempt，OCR 关闭路径只记录 Plain 的一次 attempt，然后返回 PDF 类型的解析失败。
- 任务取消异常必须立即向上传播，不能触发 `PlainPdfParser` 兜底。
- 请求 JSON 时，两个内部实现都转换为 `PdfParser` 自己定义的 JSON 结果，不能透传
  pdfreader 或 PaddleOCR 的原生结构。
- 两个实现的结果不拼接；实际成功引擎是否出现在返回值中以及字段名由 `PdfParser`
  自己定义，非 OCR 引擎为 `pdfreader`。
- PDF 的远程 OCR 超时继续使用现有
  `document_parser_api_timeout_seconds` 配置，不在 parser 内写死。

### 8.2 DOCX

- `DocxParser` 是 DOCX 类型唯一的 Parser，首选使用 `python-docx` 打开文件。
- 按正文中的实际顺序遍历段落和表格，不能先输出全部段落再输出全部表格。
- Heading 样式转换为 Markdown 标题，列表转换为 Markdown 列表，表格转换为
  Markdown 表格。
- 首期处理正文、正文内表格和基础样式；批注、修订记录、复杂绘图不作为成功条件。
- python-docx 打开失败、结构损坏或非空文件输出为空时，`DocxParser` 内部兜底到
  Docling。
- Docling 直接导出 Markdown，不与 python-docx 结果合并；实际引擎信息是否包含在
  返回值中由 `DocxParser` 自己定义。
- JSON 输出按正文顺序生成 heading、paragraph、list_item 和 table 元素。

### 8.3 DOC

- `DocParser` 是 DOC 类型唯一的 Parser。
- 旧版二进制 `.doc` 只走 Apache Tika。
- 推荐部署 Tika Server，通过现有异步 HTTP 客户端调用，避免 worker 启动时动态下载
  JAR 或隐式依赖本机 Java。
- Tika 返回 XHTML 时，先用 BeautifulSoup 清理，再转为 Markdown；返回纯文本时保留
  段落边界。
- JSON 输出从清理后的 XHTML/文本构造 `DocParser` 自己的结构，不透传 Tika 原始
  响应。
- 增加明确的 Tika Server URL 和超时配置；未配置时返回可诊断错误。

### 8.4 Markdown

- `MarkdownParser` 先使用 `Path.read_text()` 读取 UTF-8 Markdown，再交给
  `Python-Markdown` 解析。
- Markdown 输出保留读取到的源 Markdown，只处理 BOM、编码和换行符规范化；不能把
  Python-Markdown 生成的 HTML 再反向转换覆盖原文。
- Python-Markdown 生成的 HTML 用于语法校验、纯文本提取和 JSON elements 构建。
- 请求 JSON 时保留规范化后的源 Markdown，并按原顺序保存解析出的标题、段落、列表
  和表格；具体字段由 `MarkdownParser` 定义。
- 首期使用 Python-Markdown 基础语法；额外 extensions 必须通过配置显式启用，是否
  把启用项写入返回值由 `MarkdownParser` 决定，不能在 parser 内散落默认扩展。

### 8.5 TXT

- `TextParser` 直接读取文本，保留自然段。
- JSON 输出按自然段生成 paragraph 元素。
- 默认依次尝试 UTF-8-SIG、UTF-8；是否增加 GB18030 作为显式配置项待确认。
- 不默认使用 `errors="replace"` 吞掉解码错误，避免无提示地破坏正文。

### 8.6 Excel（CSV / XLSX）

- `ExcelParser` 是 CSV 和 XLSX 唯一对外暴露并注册的 Parser。两个扩展名共用同一个
  `parse(...)` 入口、工作表模型、Markdown 生成逻辑和 JSON 输出结构。
- `ExcelParser` 根据已经校验过的文件扩展名选择内部读取方式：CSV 使用
  `pandas.read_csv`，XLSX 使用 `pandas.read_excel` 和 openpyxl。这只是
  `ExcelParser` 的内部格式分支，不建立两个子 Parser，也不恢复 `TableParser`。
- CSV 作为只有一个逻辑工作表的 Excel 文档处理，工作表名称使用文件名 stem；XLSX
  按工作簿中的原始顺序保留多个工作表。
- CSV 可以接受编码和分隔符参数，并识别逗号、制表符和分号；XLSX 可以接受工作表
  选择参数。格式不适用的参数必须明确报错，不能静默忽略。
- 跳过完全空白的 XLSX 工作表；CSV 保持原始行列顺序。每个非空逻辑工作表输出
  `## 工作表名` 和一个 Markdown 表格，第一行作为表头，所有单元格执行 Markdown
  表格转义。
- 列数不足的行补空单元格，超出的列保留，不能因格式差异丢失原始二维位置。
- JSON 使用统一的 Excel 结果结构，至少包含源格式 `format` 和 `sheets`；每个 sheet
  保留 `name` 与原始二维 `rows`。JSON 单元格不能使用 Markdown 转义后的文本，
  日期时间等非 JSON 原生值应转换为稳定的可序列化值。
- XLSX 不在 parser 中计算公式，只读取工作簿中缓存的公式结果。缺少缓存值时如何
  返回警告由 `ExcelParser` 定义。
- `.xls` 不在本阶段支持范围内，不能路由到 `ExcelParser` 后再交给 openpyxl 试错。

### 8.7 PowerPoint

- `PptxParser` 仅支持 `.pptx`，使用 `pptx.Presentation(path)` 打开文件。
- 按幻灯片顺序读取；每页先输出标题，再按 shape 集合顺序提取文本框、占位符和表格。
- Markdown 输出以 `# 幻灯片 N：标题` 分隔页面，正文文本、列表和表格保持在所属
  幻灯片下。
- JSON 输出按页保存幻灯片内容，页码从 1 开始，具体字段由 `PptxParser` 定义。
- 首期提取标题、文本框、占位符、列表和表格；图表只提取可访问的标题与文本，嵌入
  图片可以记录在 `PptxParser` 自己的结果中，但不自动调用 OCR。
- 空白幻灯片保留 slide 元素；非空演示文稿全部解析为空时视为失败。
- `.ppt` 不得伪装成 `.pptx` 交给该 parser。

### 8.8 图片

- `ImageParser` 是图片类型唯一的 Parser，只负责编排现有 OCR extractor。
- 建议初始顺序保持当前行为：RapidOCR -> PaddleOCR -> UnlimitedOCR。
- 调用方显式指定 OCR 引擎时只运行该引擎。
- 保留 OCR 行顺序、置信度和引擎信息；不在图片 parser 内做文本分块。
- JSON 输出按识别顺序生成 ocr_line 元素。

### 8.9 HTML

- `HtmlParser` 使用 `BeautifulSoup(html, "html.parser")`，固定解析器以避免不同机器
  产生不同 DOM。
- 移除 `script`、`style`、`noscript`、`template` 等非正文节点。
- 优先处理 `body`；保留标题、段落、列表、链接和表格。
- 清理后的 HTML 使用现有 `markdownify` 转成 ATX 风格 Markdown。
- JSON 输出按清理后的 DOM 顺序生成 `HtmlParser` 自己的结构。

## 9. 异步与运行边界

- `pdfreader`、`python-docx`、`python-pptx`、Docling、openpyxl、Python-Markdown、
  文件读取等
  同步阻塞工作通过
  `asyncio.to_thread()` 执行，不能阻塞 FastAPI 或 ARQ 事件循环。
- PaddleOCR 和 Tika Server 使用异步 HTTP 客户端，并采用配置化超时。
- parser 不自行下载远程文件；MinIO/URL 到本地临时文件的转换仍由外层服务统一完成。
- parser 不读取数据库、Redis、Agent context 或全局业务状态。
- parser 不修改源文件。

## 10. 依赖计划

各 Parser 直接导入的第三方包必须声明到 `pyproject.toml`，并同步更新 lockfile。
`ExcelParser` 直接依赖 `pandas`，XLSX 分支同时直接依赖 `openpyxl`。

JSON 输出使用 Python 标准库支持的类型和现有 Web 框架序列化能力，不新增 JSON
依赖，也不在 parser 内进行二次字符串编码。

| 依赖 | 状态与用途 |
| --- | --- |
| `docling` | 直接依赖；仅作为 DOCX 兜底，不用于 PDF |
| `pdfreader` | 直接依赖；供 `PlainPdfParser` 使用 |
| `httpx` | 直接依赖；复用 PaddleOCR/Tika HTTP 调用 |
| `markdownify` | 直接依赖；用于 HTML/XHTML 转 Markdown |
| `python-docx` | 直接依赖；作为 DOCX 首选引擎 |
| `python-pptx` | 直接依赖；用于 PPTX |
| `pandas` | 直接依赖；供 `ExcelParser` 统一读取 CSV 和 XLSX |
| `openpyxl` | 直接依赖；作为 pandas 的 XLSX 读取引擎 |
| `beautifulsoup4` | 直接依赖；用于 HTML/XHTML 与 Markdown 结构解析 |
| Tika Server | 外部服务；通过 `TIKA_SERVER_URL` 配置，不在 Parser 内管理 JAR |
| `Python-Markdown` | 直接依赖；默认不启用额外 extensions |

若采用 Tika Server REST 方案，不需要为了 `.doc` 再引入会在本地管理 JAR 的 Python
Tika 包。

## 11. 与旧实现的迁移关系

已删除的 `src/knowledge/document_praser.py` 曾是单文件分发器，与本规范存在以下
差异：

- PDF 旧实现默认 Docling，仅在 `enable_ocr=true` 时走 OCR；目标是保留开关语义，
  由 `PdfParser` 门面编排两个内部子类，并让 Plain/pdfreader 成为 OCR 失败时的
  兜底，PDF 路径完全移除 Docling。
- DOC、DOCX、PPTX 旧实现统一交给 Docling；目标是分别使用 Tika、python-docx 和
  python-pptx。
- 旧 `.ppt` 曾交给 Docling；目标规范暂不支持，不能误路由给 python-pptx。
- 旧 XLSX 走 Docling，旧 CSV 走通用文本分支；目标是让两者统一进入
  `ExcelParser`，分别由 pandas 的 `read_excel` 和 `read_csv` 读取，再归一化为
  同一种工作表结果。
- Markdown、TXT、HTML 旧实现共用文本读取分支；目标是让 Markdown 使用
  Python-Markdown，其余格式按各自规则处理。
- 图片旧实现已使用 OCR extractor，可迁移其编排逻辑。
- 旧公共结果只以 `markdown` 字段承载正文；目标是让每个 Parser 在保持 Markdown
  默认行为的同时提供自己的 JSON 输出，不建立新的公共结果对象。

实施时建议：

1. 先建立注册表，以及每个文档领域唯一对外暴露的 Parser 和各自的数据类型。
2. 为 PDF 建立内部基类、两个实现类和 `PdfParser` 门面，并先验证 OCR 开关与兜底。
3. 实现单一 `ExcelParser`，让 CSV 和 XLSX 共用 Excel 路由与输出模型。
4. 用单元测试分别验证类型路由和其他 Parser 的内部引擎兜底顺序。
5. 重做 RAG 调用入口，使其调用 `parser/service.py`，不恢复旧的单文件分发器。
6. 保留 Parser 外层的临时文件处理和清洗/分块边界。

## 12. 验收标准

- 每个表格中列出的文档领域只注册一个 Parser，并且只进入自己的领域路由。
- 注册表中的 `csv` 和 `xlsx` 路由项都指向同一个 `ExcelParser` 类；对应扩展名、
  MIME 和显式类型仍保留各自的格式校验。
- 根目录不导出、注册表不注册 `CsvParser`、`XlsxParser` 或 `TableParser`。
- CSV 和 XLSX 都通过同一个 `ExcelParser.parse(...)` 入口，并产生同一种工作表
  Markdown/JSON 结构；内部读取方式仍由实际格式决定。
- 注册表中不存在 PaddleOCR、Docling、python-docx 等引擎级 Parser。
- PDF 注册表中只有 `PdfParser`；`BasePdfParser`、`PlainPdfParser` 和
  `OcrPdfParser` 均不可注册或从根目录 `__init__.py` 导出。
- `enable_ocr=false` 时 PDF 只调用 `PlainPdfParser`。
- `enable_ocr=true` 时 PDF 先调用 `OcrPdfParser`；成功时不调用
  `PlainPdfParser`，失败时只兜底到 `PlainPdfParser`。
- `PlainPdfParser` 只使用 `pdfreader`；`pdf_parser.py` 没有 Docling import 或调用。
- `PlainPdfParser.extract_outlines()` 能取得 PDF Catalog 中的原始 `Outlines`。
- DOCX 的首选引擎成功时，内部兜底引擎不会被调用。
- 首选引擎失败时只调用当前类型 Parser 配置的下一个引擎；attempts 是否进入返回值
  由该 Parser 决定。
- 所有类型 Parser 都明确接受 `filename`、`byte_stream` 或两者；二进制流缺少类型
  提示时不会盲猜 Parser。
- 不存在公共请求类、公共结果类或统一 `parse(...)` 签名，每个 Parser 的返回类型
  单独测试。
- 未显式选择输出模式时，每种 Parser 都默认产生 Markdown。
- 每种 Parser 都支持 Markdown 和自己的 JSON；JSON 核心结果可被标准编码器直接
  序列化。
- 格式 parser 内不执行清洗和分块。
- 单元测试使用 stub/mock 模拟 PaddleOCR 和 Tika，不依赖真实网络服务。
- 至少包含每种格式的两种输出、默认 Markdown、最小样例、空文件、损坏文件、错误
  扩展名/MIME 和兜底测试。

## 13. 待确认项

1. `.doc` 的独立 Tika Server 由哪个部署环境提供。
2. TXT 是否需要显式支持 GB18030。
3. `.xls`、旧 `.ppt`、`.json` 输入是否留到下一阶段。

## 14. 参考资料

- [Docling 支持的输入输出格式](https://docling-project.github.io/docling/usage/supported_formats/)
- [Docling DocumentConverter](https://docling-project.github.io/docling/reference/document_converter/)
- [pdfreader 官方文档](https://pdfreader.readthedocs.io/en/latest/)
- [python-docx 文档与表格 API](https://python-docx.readthedocs.io/en/latest/user/quickstart.html)
- [Apache Tika Server](https://cwiki.apache.org/confluence/spaces/TIKA/pages/148639291/TikaServer)
- [Apache Tika Microsoft Office Parser API](https://tika.apache.org/3.2.3/api/org/apache/tika/parser/microsoft/)
- [Beautiful Soup 官方文档](https://beautiful-soup-4.readthedocs.io/en/latest/)
- [openpyxl 优化读取模式](https://openpyxl.readthedocs.io/en/stable/optimized.html)
- [Python-Markdown 官方文档](https://python-markdown.github.io/)
- [python-pptx 官方文档](https://python-pptx.readthedocs.io/en/latest/)
- [python-pptx 打开演示文稿及 `.ppt` 限制](https://python-pptx.readthedocs.io/en/latest/user/presentations.html)
