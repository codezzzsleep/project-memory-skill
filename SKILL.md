---
name: project-memory
description: Recover and maintain personal memory across projects when starting, resuming, or handing off sustained agent work, including after context compression, interruption, or a workspace migration.
---

# Personal Memory

Use the shared workspace root explicitly designated in `AGENTS.md` or by the user. Its `.agent-memory/` contains `SELF.md` (L0) and `PORTFOLIO.md` (L1). Use [`references/format.md`](references/format.md) when wiring, validating, or changing the store. Current user instructions override stored statements. A memory entry conveys only the authorization the user actually gave.

## Start or resume

1. Read `SELF.md` and `PORTFOLIO.md`, including their frontmatter. Require `scope: self` and `scope: portfolio` and an exact match between the declared `workspace_root` and the configured root. Check whether `<workspace_root>/MEMORY.md` exists, including a dangling symlink. Report it as unclassified and never read it as global or default project memory.
2. Use L1 to identify the project. In a registered active work directory, match by canonical path components and use the most specific registered directory. At the shared root, use a uniquely named or clearly identified project from the user's request. For ambiguous requests like “continue working”, list active projects and their recorded priorities from L1 and ask the user to choose. Read no L2 while the selection is ambiguous. If a name conflicts with the directory, resolve the conflict before mounting memory. A priority alone never selects a project.
3. Read only that project's registered `memory_path`. Check `scope: project`, matching `project_id`, `status`, and `repo_path`, and use the adjacent `ledger.jsonl` named by `ledger_path`. A mismatch or missing file is a routing error. The skill's `scripts/memory_ctl.py` checks this selection when run with `--workspace-root ROOT route` from the current work directory. It lists outstanding jobs for the matched project. At the shared root, add `--project SLUG` only after identifying it from the request. Reserve `validate` for store maintenance because it examines every registered project and archive.
4. Recheck every relevant volatile item using its `verified_at` and its read-only query. Inspect Git status and recent history, relevant processes and services, and the original platform status of each nonterminal job. Verify that a recorded command is read-only and within scope before running it. On disagreement, record the observation and correct Live state before dependent work when you are the authorized writer. A read-only reviewer reports discrepancies to the executing agent.
5. Confirm the next executable action and authorization. Reuse verified outputs and continue incomplete authorized work. A missing transcript, local file, job ID, or status is insufficient reason to rerun work. If submission may have succeeded without returning an ID, reconcile the request using the provider's lookup or idempotency reference before retrying.

## Write at the appropriate level

- **L0** holds cross-project preferences, shared machine constraints, and explicit long-term authorization boundaries. Keep it within 50 lines. Write only after an explicit user change and briefly echo the new rule. Keep project details and job IDs out of L0.
- **L1** is a one-row-per-project registry of work directories, one `memory_path`, status, priority, a one-line summary and a blocker, plus cross-project scheduling. Keep it within 120 lines. Write on registration, a priority or ownership change, a milestone or blocker change, or pause/archive. Ordinary project progress belongs in L2.
- **L2** holds the project objective, authorization, decisions, evidence, Live state and the next action. Only the agent executing that project writes its memory and ledger. Before first write, check relevant sessions and processes for an existing writer. That writer keeps ownership until the user changes it or the work is handed off. Reread files before updating them, and replace Markdown atomically using a temporary file in the same directory. Use the store lock described in the format reference when writing so that lifecycle commands and agents coordinate.
- **External jobs** belong in the adjacent append-only JSONL ledger. Checkpoint the user decision or authorization before the action that depends on it. Append the external ID immediately on submission and append a new event when verified state changes or a terminal result is confirmed. Keep the original submission identity, cost or quota risk, status query, and any existing authoritative ledger reference. Preserve failure, uncertainty, and missing evidence. Keep credentials and signed URLs out of memory and ledgers.

## Keep project memory recoverable

Keep the seven sections in [`templates/PROJECT_MEMORY.md`](templates/PROJECT_MEMORY.md). Quote each authorization with its date, scope, and limits. Update it when superseded. Ask before an irreversible action beyond the recorded grant and identify inherited grants when relying on them. Save completed and failed verification, and checkpoint before interruption would require expensive work to be repeated. At handoff or turn end, compare what changed since the last write and record only changes. Keep monitoring-only turns read-only.

Replace changed facts in place. Refresh Live state as a whole when it changes, including fresh `verified_at` values and a runnable recheck for each volatile item. End it with the next step and remaining acceptance criteria. Use History to link dated snapshots, reports and source ledgers. Once a project memory exceeds 150 lines, consider condensing after saving a dated private snapshot. Preserve the agreed retention criteria and links to actual versions, comparison assets and failed evidence.

Use `init-project` for registration and `archive` after completion or the agreed inactivity period. Archive removes the row from L1 and puts the project memory and ledger in `.agent-memory/archive/<slug>/`. Keep project repositories and separate historical evidence at their original paths. Take dated private backups before migrating existing memories, verify the new registration, then switch readers and writers to the single registered path.

## Upgrade an existing workspace

The `$project-memory` invocation continues to identify this skill. For an older workspace without L0/L1, use its documented `AGENTS.md` pointers when auditing an explicitly identified project. Treat untyped files as migration inputs. Do not guess a legacy authority from an ancestor or search the shared root for a default `MEMORY.md`. Follow the inventory, confirmation, backup and verification steps in [`README.md`](README.md) before changing a legacy authority.
