# Tasks: Worker Stop-Case Preemption Publish

计划版本：`v0.2.0`

- [x] T1 更新 RUN-HIL-006，记录 `_finalize_run` 与 case 二次发布合同。
- [x] T2 在 `error/finished/interrupted` 三个 case 内按
  `finalize -> changed 二次发布 -> terminal_flag` 的顺序实现。
- [x] T3 更新 Worker 定向测试，覆盖 changed、二次 end 和每个 case 内的
  `terminal_flag`。
- [x] T4 执行定向 unittest、Ruff、语法检查和 diff 检查。
- [x] T5 完成后归档 v0.2.0 的 plan 和 tasks。
