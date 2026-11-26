# Personal Memory for agents

这个技能让 Agent 在多个项目间恢复工作。新会话先读个人偏好和项目索引，确定目标后才读该项目的记忆与账本。恢复前查现场状态，已提交的外部作业用原 ID 查询，避免重复执行或付费。

| 层级 | 文件 | 内容 |
| --- | --- | --- |
| L0 | `.agent-memory/SELF.md` | 长期个人偏好、授权边界、本机共用约束，最多 50 行 |
| L1 | `.agent-memory/PORTFOLIO.md` | 项目目录、唯一记忆路径、状态、优先级和跨项目排期，最多 120 行 |
| L2 | `MEMORY.md` 与相邻的 `ledger.jsonl` | 项目决策、授权、证据、下一步和外部作业历史 |

每份 Markdown 记忆用 YAML `scope` 声明作用域。共享根目录中的 `MEMORY.md` 会触发提示，Agent 通过项目注册表选择记忆。一个项目也可以登记多个工作树，所有工作树共用同一份权威记忆。

## 安装和接线

```bash
git clone https://github.com/codezzzsleep/project-memory-skill ~/.codex/skills/project-memory
```

已有 Git 安装可快进更新。调用名仍是 `$project-memory`。管理脚本使用 Python 3.9+ 标准库和 POSIX 文件锁。在支持 `AGENTS.md` 的其他 Agent 中，可以从本地工作区指令引用 `SKILL.md`。

```bash
workspace=/absolute/path/to/workspace
skill_dir="$HOME/.codex/skills/project-memory"
python3 "$skill_dir/scripts/memory_ctl.py" --workspace-root "$workspace" init-workspace
python3 "$skill_dir/scripts/memory_ctl.py" --workspace-root "$workspace" init-project example \
  --repo-path "$workspace/example-repo" --priority high --summary 'Preparing first release'
```

在共享工作区的本地 `AGENTS.md` 指明入口和根目录。将示例路径替换为安装和工作区的实际绝对路径。

```markdown
# Personal memory

Use the `project-memory` skill at `/path/to/skills/project-memory/SKILL.md`
for sustained work and recovery. The shared workspace root is `/path/to/workspace`.
Start with its `.agent-memory/SELF.md` and `.agent-memory/PORTFOLIO.md`.
At the shared root, never load `MEMORY.md` as global or default project memory.
Only the executing agent writes the selected project's memory and ledger.
```

## 日常管理

- `route` 在登记目录内自动选择项目。共享根目录可传 `--project <slug>`，或让命令返回候选和优先级。已选中项目时，结果包含该项目的记忆路径和未终结作业。
- `validate` 检查全部登记和归档，报告无效元数据、缺失文件、重复路径、超行以及共享根目录的遗留 `MEMORY.md`。
- `init-project <slug>` 创建并登记 L2。重复提供 `--repo-path` 可登记多个现有工作目录。共享根目录省略此参数时，以新建的 L2 目录为项目工作目录。
- `archive <slug>` 将完成或达到约定停更周期的项目记忆和账本移入 `archive/<slug>/`，并移出 L1 项目表。归档前核对写入者、作业和证据引用。

私有记忆可放在集中目录，或放在经确认由 Git 忽略的项目内目录。凭据仅记录加载方式。个人底座可以独立做本地 Git 版本管理，原始证据和备份的访问权限按其内容管理。

## 迁移现有记忆

1. **只读盘点**。读现有技能和 `AGENTS.md`，确认每个项目的权威记忆、工作树、历史快照、账本、活跃写入者及缺失证据。列出源路径、目标路径、元数据和账本处理、备份路径，交由用户确认。
2. **备份与迁移**。在私有目录做带日期的备份，记录源文件哈希。给 L2 加 `scope: project`、`project_id`、`status`、`repo_path`、`ledger_path` 和 `updated_at`。按真实来源整理串项目的内容，保留授权原话和限制。将可核验的外部作业补到同目录 JSONL，并保留其原始账本。将证据链接解析为新位置仍可访问的路径。为每个项目登记唯一入口并切换读写者，处理共享根遗留文件。来源缺失时记录缺口，待权威路径明确后再挂载。
3. **验证**。运行 `validate`，检查保留的证据和原账本。用隔离工作区验证模糊启动、显式路由、目录路由、根目录隔离、作业防重、分层写回与归档。

文件格式和并发写入见 [格式说明](references/format.md)，可复跑的场景见 [验收报告](tests/ACCEPTANCE.md)。
