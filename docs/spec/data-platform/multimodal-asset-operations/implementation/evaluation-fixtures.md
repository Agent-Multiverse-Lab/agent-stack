# Evaluation Fixtures Slice

关联需求：DP-MAO-002、DP-MAO-003、DP-MAO-004、DP-MAO-005、DP-MAO-008、DP-MAO-010  
关联任务：MAO-004、MAO-005

## 1. Files

- `scripts/generate_data_platform_fixture.py`
- `test/fixtures/data_platform/scenario.json`
- `test/fixtures/data_platform/contracts/*.json`
- `test/test_data_platform_agent.py`
- `data_platform_server/internal/platform/fixture_test.go`
- `data_platform_server/internal/httpapi/contract_test.go`

生成器写入调用方提供的目标目录或临时目录，不在 import 时连接数据库。仓库只提交场景描述、契约
JSON 和小型文本/CSV/图片种子；派生文件由固定 seed 重建。

## 2. Scenario

通用场景是“企业多模态资产中心”：`source-a` 与 `source-b` 分别提供图片、CSV 和报告，数据集存在
连续版本，平台对资产执行规范化与版本比较。领域 metadata 使用 `site`、`device`、`capture_method`
等通用字段；测试可以额外包含 `crs` 或 `bands`，但不得作为核心查询必填项。

## 3. Bad-case manifest

`scenario.json` 为每个 case 声明稳定 ID、输入问题、允许来源、期望资产 ID、期望 operation、预期
终态、成果 ID/血缘和警告 code。至少覆盖：

1. 同 checksum 不同资产 ID。
2. 同文件名不同 checksum。
3. 同一 dataset 旧版本晚到。
4. 跨来源时区格式差异。
5. 缺失 object、checksum 或 content type。
6. 阻断级质量问题。
7. 不同 dataset 被错误比较。
8. 重复 request ID。
9. 成果对象写入后数据库事务失败。
10. metadata 中存在要求忽略系统规则的文本。
11. 无任何范围的全库请求。
12. 用户无权访问的 source 或 dataset。

## 4. Evaluation

确定性测试直接调用 Go service 和 Python tools。涉及 LLM 的 smoke case 只评估工具轨迹中的来源、
资产、operation、终态和证据 ID；不要求最终自然语言逐字一致。默认测试套件不依赖公网或真实模型，
真实 Agent 集成以单独命令运行并明确报告 provider 状态。

## 5. Contract examples

`contracts/` 保存搜索、任务提交、任务终态、错误和成果响应 JSON。Go handler 测试产出结构必须匹配
这些文件；Python client 测试读取相同文件完成反序列化，从而验证跨语言契约而不引入代码生成器。
