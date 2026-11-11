---
name: project-memory
description: Read and maintain durable project decisions, evidence, live jobs, and recovery checkpoints when continuing work with an active MEMORY.md, migrating repositories, or recovering after context compression. Also use when the user requests persistent project memory.
---

# Project Memory

Keep the user's purpose, accepted decisions, permissions, evidence, and next executable step recoverable without asking them again. Memory supports the active task; it never replaces a newer user instruction.

## Read before acting

Follow the applicable AGENTS.md to locate the authoritative MEMORY.md. Read it before the first project action when starting work, resuming after an interruption, recovering from context compression, or switching workspaces. If no location is designated, locate an existing memory in the project or its workspace before creating one. Keep one authority; use links from other checkouts rather than competing current-state files.

Before asking a question or making a consequential workflow choice, consult the relevant memory sections. Reuse recorded authorization and configuration locations. Verify volatile state such as SSH availability, API authentication, or Git head with tools; distinguish a prior successful check from current availability.

Read only the linked evidence needed for the next action. A compressed conversation is a lead, not proof that a job failed, a file disappeared, or an earlier decision was revoked.

## Write at decision boundaries

Update memory immediately when:

- The user changes the objective, repository, required deliverables, constraints, or authorization.
- A design decision changes what will be retained, migrated, removed, or presented. Record its reason.
- A meaningful implementation stage or verification completes or fails.
- A paid/external job is created, yields, finishes, or is uncertain. Record its task ID and durable ledger path before continuing; the ledger remains authoritative.
- Work switches between local and remote environments or repositories.
- You are about to end a turn, hand off, or approach context compression.

For a new user decision, write the accepted instruction and its reason before dependent work. For an external job, persist the identity in its durable ledger as part of creating it; then point memory to the ledger. Do not defer the only recovery record until a final response.

Do not wait for a user reminder. During a long stage without these events, checkpoint when interruption would require repeating expensive actions. A tool yield or a phase transition is an opportunity to check for unrecorded state; do not append a log for every tool call.

## Preserve useful state

Keep memory concise and operational. Record:

- The objective and why the chosen approach serves it.
- User decisions and required deliverables, separate from optional suggestions.
- Authorizations already granted and genuine conditions still missing.
- The authoritative repository, branch/head, environment, credential file locations, and runtime commands.
- What actually completed, verification results, and evidence paths.
- Running jobs, partial mutations, failed attempts, and actions that must not be repeated.
- The next concrete action and remaining acceptance criteria.

For repository migrations and showcase work, preserve the agreed retention criteria: which core versions, source snapshots, input assets, generated assets, comparisons, rejected examples, and results must remain available, and why they support the user's presentation. Point to those artifacts. A list of version names alone does not preserve an iteration.

Replace superseded current-state statements instead of repeatedly appending conflicting plans. Separate durable decisions from current status and the next action. Keep a dated checkpoint outside the public repository before substantially condensing existing memory, and link it for recovery. Reference detailed reports and ledgers rather than copying them into every checkpoint.

Never store credential values, tokens, or passwords. Store their location and safe loading instructions. Keep private operational memory outside a public repository; public project status and technical milestones are separate deliverables.

## Recovery check

After reading memory, inspect files and running jobs before retrying. Continue incomplete authorized work. Do not repeat questions, recreate repositories, resubmit known paid tasks, or discard assets because they are absent from the compressed conversation.

When memory and observed state disagree, record the observation and correct current status. Do not erase the user's intent or change the task to fit what happens to be implemented. Only ask about an actual unresolved dependency after checking memory and available evidence.

At a checkpoint, confirm that the next reader can identify the active repository, understand why the work is being done this way, find evidence, and execute the next step. “Continue working” alone is not a useful checkpoint.

## Make reminders discoverable

For a workspace using this skill, maintain a short AGENTS.md entry naming this skill and the authoritative memory path, with the start/resume, decision, job, verification, and end-of-turn triggers. Keep that entry accessible from each active repository. Link private memory from machine-local instructions; keep publishable technical decisions and version evidence in the repository's documentation.

This skill provides instructions at work boundaries, not a background timer. Do not claim that installing it creates automatic file writes or guarantees recovery without checkpoints. Read the installed SKILL.md directly in the current session if its catalog has not refreshed.
