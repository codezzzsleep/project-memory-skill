# project-memory

一个给 Codex 用的技能（skill）：让持续多天、跨多个会话的项目，在上下文被压缩、会话崩溃或换一个会话接手之后，不用再问用户就能接着做下去。

它不是后台程序，也不会自动写文件。它是一份写给 agent 的工作约定：什么时候读项目记忆、什么时候写、写什么、哪些东西必须先落盘再动手。

## 它解决什么问题

长任务里最贵的错误通常不是代码写错，而是恢复时出错：

- 重复提交已经付过费的外部任务；
- 把已经跑完的实验重跑一遍；
- 重新问用户早就回答过的问题、早就给过的授权；
- 因为压缩后的对话里没提到，就以为某个文件或决定不存在了。

这个技能的核心做法是：

1. **先落盘，再做依赖它的事。** 用户的新决定、外部任务的身份，在动手之前就写下来；任务身份写进它自己的账本，记忆只指向账本。
2. **记忆是线索，工具才是证据。** 恢复时先读记忆，再用工具核实进程、账本、Git 状态，然后才决定要不要重试。
3. **一个工作区只有一份权威记忆**，其它位置只放指向它的链接。

## 仓库内容

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 技能正文，agent 实际读的就是它 |
| `agents/openai.yaml` | Codex 界面里的显示名、简介和默认提示 |

## 安装

仓库根目录就是技能目录，直接克隆到 Codex 的技能目录下：

```bash
git clone https://github.com/codezzzsleep/project-memory-skill ~/.codex/skills/project-memory
```

## 在工作区里接线

技能本身不知道你的记忆文件放在哪。在工作区的 `AGENTS.md` 里加一小段，写明技能路径、权威记忆的路径，以及谁可以写它，例如：

```markdown
# Durable project memory

Use the local `project-memory` skill at `~/.codex/skills/project-memory/SKILL.md`
and the authoritative `/path/to/workspace/MEMORY.md` for sustained work here.
Read both before starting or resuming work, especially after context compression.
Only the agent executing the work writes MEMORY.md; reviewing or advising agents
read it and report disagreements.
```

`AGENTS.md` 会被这个工作区里的所有 agent 读到，包括只是来查看状态或做评审的。所以这里不要写"每次结束前都更新记忆"这类不分角色的要求，否则旁观的 agent 也会去写。

记忆文件通常含有私有的操作细节（路径、作业、授权），不要放进公开仓库；密钥的值任何时候都不写进去，只写它存放的位置和加载方式。

## 记忆文件的形状

技能要求 `MEMORY.md` 按固定顺序分成七节：

| 节 | 内容 |
| --- | --- |
| Objective | 用户要什么、为什么这样做；必须交付的和可选建议分开 |
| Authorization | 每项授权一条：用户原话、日期、覆盖范围和限制 |
| Standing rules | 约束、冻结项、不能重复的动作，各带原因 |
| Done, do not redo | 已完成的阶段，各带验证结果和证据路径 |
| Live state | 一切会自己变化的状态，带时间戳和复核方式；末尾是下一步和剩余验收条件 |
| Environment | 活跃仓库、运行命令、凭据从哪里加载 |
| History | 指向快照、报告、账本的链接 |

几条关键约定：

- 事实变了就原地替换旧说法；Live state 每次整节重写并更新时间。
- 文件里没有流水日志，按时间顺序的经过写到报告或账本里，由 History 链接过去。
- 超过 150 行就压缩，压缩前先在公开仓库之外留一份带日期的副本。
- 已记录的授权只在它写明的范围内复用；范围之外的不可逆操作要先问用户。

## 版本

| 版本 | 说明 |
| --- | --- |
| `v0.1.0` | 初始版本，从实际使用中的安装目录原样上传 |
| `main`（未打标签） | 修订版，待评审。相对 `v0.1.0`：固定了记忆文件的分节和写法；规定只有执行中的 agent 可以写；授权条目要带原话、日期和范围；回合结束时没有变化就不写；易变状态集中到 Live state 并附复核方式 |

