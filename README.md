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

技能本身不知道你的记忆文件放在哪。在工作区的 `AGENTS.md` 里加一小段，写明技能路径和权威记忆的路径，例如：

```markdown
# Durable project memory

Use the local `project-memory` skill at `~/.codex/skills/project-memory/SKILL.md`
and the authoritative `/path/to/workspace/MEMORY.md` for sustained work here.
Read both before starting or resuming work, especially after context compression.
```

记忆文件通常含有私有的操作细节（路径、作业、授权），不要放进公开仓库；密钥的值任何时候都不写进去，只写它存放的位置和加载方式。

## 版本

| 版本 | 说明 |
| --- | --- |
| `v0.1.0` | 初始版本，从实际使用中的安装目录原样上传 |
