# Store format

The workspace root is declared in its local `AGENTS.md` or supplied by the user. Use absolute paths in the store. `--workspace-root` takes this root and defaults to the command's current directory. The CLI never searches parent directories for memory files.

```text
<workspace_root>/
  AGENTS.md
  .agent-memory/
    SELF.md
    PORTFOLIO.md
    projects/<project_id>/MEMORY.md
    projects/<project_id>/ledger.jsonl
    archive/<project_id>/MEMORY.md
    archive/<project_id>/ledger.jsonl
```

Projects may instead use a registered repository-local `MEMORY.md` and adjacent `ledger.jsonl`. Keep a single registered path. Extra checkouts use their registration to find it. Before moving memory, make external evidence references absolute or update them to remain valid at the destination. Keep relative links for evidence that moves alongside the memory, such as the adjacent ledger.

## Markdown frontmatter

Use the flat YAML scalar mapping shown in the templates. Start with `---` on the first line and end the mapping with another `---`. Keys are unique. Values may be plain scalars, single-quoted scalars, or JSON-escaped double-quoted strings. Nested YAML and multiline scalars are outside the format. Write UTC timestamps as `YYYY-MM-DDTHH:MM:SSZ`. The validator also accepts UTC offsets of `+00:00` and fractional seconds.

| File | Required fields in addition to `scope` and `updated_at` |
| --- | --- |
| `SELF.md` | `owner` |
| `PORTFOLIO.md` | `workspace_root` |
| Project `MEMORY.md` | `project_id`, `status`, `repo_path`, `ledger_path` |

The respective `scope` values are `self`, `portfolio`, and `project`. Project IDs use lowercase letters and digits with optional single hyphens between parts. Project `status` is `active`, `paused`, or `archived`. The primary work directory in L2 agrees with the first path in L1. Archive metadata keeps the original `repo_path` and points to the archived ledger.

## Project registry

Use the template's header and separator. Put one project on each contiguous table row. `repo_paths` is a JSON array of absolute directory strings, primary path first. `memory_path` is one absolute path to a file named `MEMORY.md`. Use `unset` for an unassigned priority and `-` when there is no blocker. Escape literal `|` as `\|` and `\` as `\\` within cells, including JSON escapes in `repo_paths`.

```markdown
| project_id | repo_paths | memory_path | status | priority | summary | blocker |
| --- | --- | --- | --- | --- | --- | --- |
| example | ["/work/example", "/work/example-repair"] | /work/.agent-memory/projects/example/MEMORY.md | active | high | First release in review | - |
```

Keep paused projects in the registry for deliberate selection. Directory routing applies to active projects. `route` returns `selection: choose` and active project summaries when the current directory and explicit selection yield no match. When selected, it returns the validated paths and `pending_jobs` for that project. Both cases report any legacy shared-root `MEMORY.md` without opening it. `validate` returns a nonzero exit code for findings.

## External job events

Use one JSON object per line and append without rewriting earlier events. An empty ledger is valid. Each event carries `job_id`, `platform`, `purpose`, `submitted_at`, `cost_risk`, `status_query`, `status`, and `verified_at` as nonempty strings. Statuses are `submitted`, `queued`, `running`, `unknown`, `succeeded`, `failed`, and `cancelled`. The last three are terminal. The latest event for `(platform, job_id)` describes the current known state and keeps the original `submitted_at`.

```jsonl
{"job_id":"fixture-7","platform":"local-test","purpose":"verify job recovery","submitted_at":"2026-01-01T00:00:00Z","cost_risk":"none","status_query":"cat /tmp/example-fixture/fixture-7.status","status":"running","verified_at":"2026-01-01T00:00:00Z"}
```

Keep original ledgers and allow evidence pointers in events, such as `source_ledger`. Verify that a status query reads the named job and is authorized before executing it. The management script parses queries as strings. Missing job identities and untriggered work belong in the memory or linked verification report until a provider ID is known. Preserve the uncertainty of an interrupted submission and use its reference for reconciliation.

## Write coordination

The management CLI uses shared and exclusive advisory locks on the `.agent-memory` directory. For agent-managed L2 writes, hold a shared store lock after establishing that you are the project's sole writer. For editing L1, hold an exclusive store lock, reread the current version, apply the one row change, and replace the file atomically. On Linux, `flock --shared "$workspace/.agent-memory" command` and `flock --exclusive "$workspace/.agent-memory" command` use the same lock. Keep a lock only during local reads and writes. For JSONL, append complete lines, flush them before continuing, and retain the prior records.

`init-project` and `archive` prepare the destination pair before publishing the registry update. Until then the original registry determines routing. The archive operation removes the original files after the archive and registry are published. If cleanup is interrupted, check the archive and reconcile any remaining originals before reuse. Confirm the sole writer before moving a project and preserve separate evidence files.
