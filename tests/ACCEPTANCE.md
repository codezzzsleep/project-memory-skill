# Acceptance report

The suite creates fresh temporary workspaces and launches the CLI in separate processes. It traces the files opened during routing. Three independent Agent sessions also exercised the skill in a temporary workspace with two registered projects, a shared-root legacy file, and a read-only job-status fixture.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

| Case | Command or observation | Result |
| --- | --- | --- |
| T1. Ambiguous shared-root start | `route` opened only `SELF.md` and `PORTFOLIO.md` and returned active projects with priorities. Given “继续工作”, the Agent read those layers and asked the user to select `north` or `south`. | Pass |
| T2. Named project | `route --project north` selected the registered memory and ledger. The Agent opened only north's L2 and ran `git status --short`, `git log -1 --oneline`, and `ps -p 1 -o comm=` to verify the checkout and supervisor. | Pass |
| T3. Project checkout | With `cwd` under `north/src`, `route` selected north and the Agent verified its Git and job state without a project name in the request. The suite also checked an alias containing spaces and a pipe, and rejection of a conflicting explicit selection. | Pass |
| T4. Legacy shared-root memory | `validate` reported the unclassified `MEMORY.md` with exit status 1. Open traces and the Agent's metadata check showed that the legacy file's content stayed outside startup. | Pass |
| T5. Job recovery | A new `route --project north` process returned the original `render-fixture` ID. The Agent ran its recorded `cat` status query and observed `render-fixture running`, with no submission. The suite also verified preservation of older submitted and failed events. | Pass |
| T6. Project update and archive | An L2 edit left `PORTFOLIO.md` byte-identical. `archive` removed the active row, updated the archived metadata and preserved the ledger byte for byte. `validate` then passed with both layer budgets satisfied. | Pass |

All 20 automated tests passed, including invalid frontmatter or ledger data, duplicate paths, concurrent registrations, and an archive destination conflict. The skill frontmatter passed the skill-creator validator. Git, process and job verification used temporary fixtures, with the job status served by a local file.
