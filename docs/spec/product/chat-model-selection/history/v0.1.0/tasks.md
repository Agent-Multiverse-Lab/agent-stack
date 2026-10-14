# Tasks: Chat Model Selection

## Ordered work

1. 从现有 Provider 配置生成模型名称、版本和 icon 元数据。
2. 增加 Redis read-through cache，并接入 `/api/models`。
4. 实现输入区模型选择组件，并由 `useModelStore` 加载目录和维护选择状态。
5. 将 model ID 传入 Run metadata 和 Agent runtime context。
6. 完成后端、前端与 diff 验证。

## Done Conditions

- cache miss 从 config 构建并回填，TTL 内直接读取 Redis；
- 公开字段不包含密钥、客户端对象或推理内容；
- 前端不写死模型选项；
- 非法 model ID 在创建 Run 前被拒绝；
- 运行期间模型选择不可变；
- 所有定向检查通过并如实报告。
