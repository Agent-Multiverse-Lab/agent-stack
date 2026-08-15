# Knowledge Evaluation Spec

## 1. Context

知识检索能力需要可量化评估能力，但不作为主运行时路径强制依赖。

## 2. Requirements

### K-EVA-001
评估能力应与主查询路径解耦，可独立启停。

### K-EVA-002
评估输入字段标准化（`query/response/context`），便于复现实验集。

### K-EVA-003
不得改变 `search` 的默认行为；评估结果只写入外部实验记录或脚本产物。

## 3. Acceptance

- 默认运行路径不受评估模块影响
- 有独立脚本/接口可复现实验数据
