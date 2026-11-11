---
name: project-memory
description: Use when starting, resuming, or handing off sustained work in a workspace that has a MEMORY.md, after context compression or a crashed session, when migrating repositories, or when the user asks for persistent project memory.
---

# Project Memory

Keep the user's purpose, accepted decisions, permissions, evidence, and next executable step recoverable without asking them again. Memory supports the active task; it never replaces a newer user instruction.

A session can end without warning. The safety net is what was written before the dependent work started: a decision in memory, a job identity in its ledger. Nothing that matters waits for an end-of-turn write.

## Read before acting

Follow the applicable AGENTS.md to locate the authoritative MEMORY.md. Read it before the first project action when starting work, resuming after an interruption, recovering from context compression, or switching workspaces. If no location is designated, locate an existing memory in the project or its workspace before creating one. Keep one authority; other checkouts link to it.

Memory is a lead; tools are proof. After reading, inspect files, ledgers, and running jobs before retrying anything, and re-check every item under Live state. A compressed conversation is also only a lead: it does not show that a job failed, a file disappeared, or a decision was revoked.

Continue incomplete authorized work. Do not repeat questions, recreate repositories, resubmit known paid tasks, or discard assets because they are absent from the compressed conversation. Before asking a question or making a consequential workflow choice, consult the relevant section first. Read only the linked evidence the next action needs.

## One writer

Only the agent currently executing the work writes MEMORY.md. An agent that is reviewing, advising, or answering a status question reads it, and reports any disagreement with what it observes to the user or the executing agent; it writes nothing.

Before the first write in a session, check whether another session is still active in the workspace (processes, session logs). If one is, it remains the writer until the user says otherwise.

To write, re-read the file, apply the change, write the result to a temporary file in the same directory, and rename it over MEMORY.md.

## When to write

Write immediately when:

- The user changes the objective, repository, required deliverables, constraints, or authorization. Write the instruction and its reason before the work that depends on it.
- A design decision changes what will be retained, migrated, removed, or presented. Record its reason.
- A meaningful implementation stage or verification completes or fails.
- A paid or external job is created, yields, finishes, or is uncertain. Its identity goes into its durable ledger as part of creating it; memory points to the ledger, and the ledger stays authoritative.
- Work switches between local and remote environments or repositories.
- During a long stage, an interruption now would force expensive actions to be repeated.

At the end of a turn or before a handoff, compare the file with what changed since the last write. If a decision, job, verification result, or environment changed, write it. If nothing changed, as after a status question or a read-only check, write nothing.

## File shape

MEMORY.md has these sections, in this order:

1. **Objective**: what the user wants and why the chosen approach serves it. Required deliverables are listed apart from optional suggestions.
2. **Authorization**: one entry per grant, in the form given below.
3. **Standing rules**: constraints, frozen items, and actions that must not be repeated, each with its reason.
4. **Done, do not redo**: completed stages, each with its verification result and evidence path.
5. **Live state (as of `<UTC time>`)**: everything that can change while the file stays the same, such as branch head, running jobs, budget counts, disk space, and service availability. Each item names the command or ledger that re-checks it. The section ends with the next concrete action and the remaining acceptance criteria.
6. **Environment**: active repository, runtime commands, and where credentials are loaded from.
7. **History**: links to snapshots, reports, and ledgers.

Every bullet states one fact, in one or two full sentences that a reader who was not in the session can follow.

A changed fact replaces the old statement where it stands. Live state is rewritten as a whole, with a new time, each time any of it changes. MEMORY.md has no running log: an account of what happened, in order, goes into a report or ledger that History links to.

When the file passes 150 lines, condense it. First save a dated copy outside any public repository and link it under History.

For repository migrations and showcase work, Standing rules carries the agreed retention criteria: which versions, source snapshots, input assets, generated assets, comparisons, rejected examples, and results must remain available, and why. Point to the artifacts; a list of version names alone does not preserve an iteration.

Credential values, tokens, and passwords are never written here; record where they are stored and how to load them. Private operational memory stays outside public repositories; public project status is a separate deliverable.

## Authorization entries

Each entry records the user's words, the date, and what the grant covers, including any limit the user stated.

Reuse a grant for what it covers without asking again. For an irreversible action the entry does not name, such as deleting data or evidence, rewriting published history, or spending past a recorded cap, ask first. A session that inherits grants names the ones it is relying on in its first report to the user. When the user narrows or withdraws a grant, replace the entry.

## When memory and observation disagree

Record the observation and correct Live state. Do not erase the user's intent or change the task to fit what happens to be implemented. Ask only about an actual unresolved dependency, after checking memory and the available evidence.

## Check before handing off

A reader holding only MEMORY.md and the repository can answer all of these:

- Which repository is active, and why is the work being done this way?
- What is finished and must not be redone?
- What is running, and where is its ledger?
- What is authorized, and by which words?
- What is the next action? "Continue working" is not an answer.

## Wiring

A workspace using this skill keeps a short AGENTS.md entry that names this skill, the authoritative memory path, and the rule that only the executing agent writes it. Keep that entry reachable from each active repository. Link private memory from machine-local instructions; keep publishable technical decisions and version evidence in the repository's documentation.

This skill gives instructions at work boundaries. It is not a background timer, and installing it does not create automatic file writes or guarantee recovery without checkpoints. If the skill catalog has not refreshed, read the installed SKILL.md directly.
