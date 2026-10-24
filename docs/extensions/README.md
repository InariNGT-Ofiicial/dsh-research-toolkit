# 桥接研究材料

从 [中文接入研究指南](../bridge-research-guide.md) 开始。

- [candidate.template.json](candidate.template.json)：复制后填写候选证据；默认 blocked。
- [candidate.schema.json](candidate.schema.json)：验证结构和结论门槛，不能验证证据真实性。
- [python_wrapper.template.py](python_wrapper.template.py)：目标官方 API 包装层骨架，默认 exit 2。
- [native_adapter.template.py](native_adapter.template.py)：真实 compiler 契约骨架，默认 ready false。

这些文件只作开发模板，不会被运行时发现或自动加载。未知软件参数留在明确的待实现
函数中；原型需要官方接口、独立科学判据和真实 DSH Agent 验收后，才能显式并入源码。
