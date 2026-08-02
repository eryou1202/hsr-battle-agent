# Git 维护流程

## 1. 仓库定位

本项目采用单仓库结构。代码按职责拆分，游戏版本数据通过快照、差分、迁移和兼容记录
管理，不覆盖旧版本。原始数据和生成产物不进入普通 Git 历史；可复现信息放在
`registry/`、`configs/`、`schemas/` 和文档中。

## 2. 日常开发

开始工作：

```powershell
cd D:\HSR_Battle_Agent\hsr-battle-agent
git switch main
git pull --ff-only origin main
git switch -c feat/<module>-<topic>
```

保存阶段成果：

```powershell
git status
git add <明确的文件或目录>
git diff --cached
git commit -m "feat(<module>): <summary>"
```

合入主线：

```powershell
git switch main
git pull --ff-only origin main
git merge --ff-only feat/<module>-<topic>
git push origin main
git branch -d feat/<module>-<topic>
```

若分支不能快进合并，先在功能分支整理：

```powershell
git switch feat/<module>-<topic>
git rebase main
git switch main
git merge --ff-only feat/<module>-<topic>
```

## 3. 数据版本维护

不要把完整游戏数据直接提交。每个游戏版本至少记录：

- 客户端版本；
- 私服或实验环境版本；
- 原始来源路径；
- 文件数量、大小和哈希；
- 解包工具版本；
- 标准化 Schema 版本；
- 与上一版本的差分摘要；
- 已知兼容性问题。

建议记录位置：

```text
registry/game_versions/<game-version>.yaml
registry/data_snapshots/<snapshot-id>.json
docs/version_notes/<game-version>.md
```

建议快照 ID：

```text
hsr-<game-version>-<YYYYMMDD>-<source>
```

例如：

```text
hsr-4.4.52-20260802-private-server
```

## 4. 版本标签

只为可运行或可验证的集成里程碑打标签：

```powershell
git tag -a v0.1.0 -m "First traceable data pipeline"
git push origin v0.1.0
```

建议早期里程碑：

- `v0.1.0`：数据链可追踪；
- `v0.2.0`：首个真实技能沙箱闭环；
- `v0.3.0`：通用 Ability 解释器；
- `v0.4.0`：完整战斗沙箱；
- `v0.5.0`：搜索排轴；
- `v0.6.0`：策略模型；
- `v1.0.0`：实时顾问可用版本。

## 5. 回退原则

撤销尚未提交的单个文件：

```powershell
git restore <file>
```

撤销暂存：

```powershell
git restore --staged <file>
```

撤销已经推送的提交，优先创建反向提交：

```powershell
git revert <commit>
git push origin main
```

不要在已经推送的 `main` 上随意执行 `reset --hard` 和强制推送。

## 6. 大文件

普通 Git 不适合保存大型模型、数据集和游戏资源。默认将这些产物保存在本地或外部
对象存储，并在仓库中记录：

- 文件名；
- SHA-256；
- 生成命令；
- 输入快照；
- 模型或数据版本；
- 保存位置。

确实需要版本控制的少量大文件，先评估 Git LFS，不要直接 `git add`。
