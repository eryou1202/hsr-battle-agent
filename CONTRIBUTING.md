# Contributing

## 分支

- `main`：始终保留可解释、可回退的稳定状态。
- `feat/<module>-<topic>`：功能开发。
- `fix/<module>-<topic>`：缺陷修复。
- `refactor/<module>-<topic>`：不改变外部行为的重构。
- `chore/<topic>`：仓库、依赖、脚本和文档维护。

模块建议使用：

- `unpacker`
- `data`
- `trace`
- `simulator`
- `planner`
- `model`
- `frontend`
- `runtime`
- `contracts`

示例：

```text
feat/unpacker-version-snapshot
feat/simulator-minimal-damage
feat/planner-beam-search
fix/frontend-trace-table
chore/repository-bootstrap
```

## 提交信息

格式：

```text
<type>(<scope>): <summary>
```

常用类型：

- `feat`：新增能力
- `fix`：修复问题
- `docs`：文档
- `test`：测试
- `refactor`：重构
- `perf`：性能优化
- `data`：版本清单、Schema 或小型可审计数据
- `chore`：仓库和工具维护

示例：

```text
chore(repo): initialize project skeleton
data(registry): add game version 4.4.52 manifest
feat(unpacker): add versioned extraction entrypoint
test(simulator): add basic attack golden trace
```

## 提交前检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/git/check_repository.ps1
git diff --check
git status
```

禁止提交：

- `.env`、密钥、账号信息；
- 游戏客户端或私服二进制；
- 原始解包数据；
- 大型 Trace、训练集和模型权重；
- 无法说明来源和游戏版本的数据快照。
