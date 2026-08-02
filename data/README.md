# Data Layout

所有大型数据默认不提交 Git。每个正式 Artifact 必须有 `manifest.json`。

```text
sources/          原始来源快照，只读
extracted/        指定解包器版本的提取结果
normalized/       指定 Schema 版本的标准化数据
diffs/            版本差分和影响报告
traces/           客户端运行时 Trace
scenarios/        固定战斗场景
episodes/         沙箱轨迹
datasets/         模型训练/评估数据集
model_artifacts/  模型权重、配置和评估报告
```
