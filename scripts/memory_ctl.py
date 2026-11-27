#!/usr/bin/env python3
"""Maintain the explicitly configured personal memory store."""

import argparse
import csv
import fcntl
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)")
FIELDS = {
    "self": {"owner"},
    "portfolio": {"workspace_root"},
    "project": {"project_id", "status", "repo_path", "ledger_path"},
}
TERMINAL = {"succeeded", "failed", "cancelled"}
JOB_STATUSES = {"submitted", "queued", "running", "unknown"} | TERMINAL
JOB_FIELDS = (
    "job_id", "platform", "purpose", "submitted_at", "cost_risk",
    "status_query", "status", "verified_at",
)
COLUMNS = ("project_id", "repo_paths", "memory_path", "status", "priority", "summary", "blocker")
PROJECT_LINE_BUDGET = 150


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_timestamp(value):
    if not UTC_TIMESTAMP.fullmatch(value):
        raise ValueError(f"expected a UTC timestamp, got {value!r}")
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_slug(slug):
    if not SLUG.fullmatch(slug):
        raise ValueError(f"invalid project_id {slug!r}")


def absolute(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"expected an absolute path, got {value!r}")
    return path


def project_memory_path(value, root):
    declared = absolute(value)
    path = declared.resolve()
    if root / "MEMORY.md" in (Path(os.path.abspath(declared)), path):
        raise ValueError("shared-root MEMORY.md cannot be used as project memory")
    if declared.name != "MEMORY.md" or path.name != "MEMORY.md":
        raise ValueError("memory_path must identify a MEMORY.md")
    return path


def yaml_scalar(raw):
    if raw.startswith('"'):
        value, end = json.JSONDecoder().raw_decode(raw)
    elif raw.startswith("'"):
        quoted = re.match(r"'(?:[^']|'')*'", raw)
        if quoted is None:
            raise ValueError("unterminated quoted scalar")
        value = quoted[0][1:-1].replace("''", "'")
        end = quoted.end()
    else:
        value = re.split(r"\s+#", raw, maxsplit=1)[0].rstrip()
        if re.match(r"^(?:[-?:](?:\s|$)|[!&*\[\]{},#|>@`%])", value) or re.search(r":(?:\s|$)", value):
            raise ValueError("expected a plain or quoted scalar")
        end = len(raw)
    tail = raw[end:]
    if tail and not re.fullmatch(r"[ \t]+(?:#.*)?", tail):
        raise ValueError("unexpected text after a quoted scalar")
    if not isinstance(value, str) or not value.strip() or any(ord(ch) < 32 for ch in value):
        raise ValueError("expected a nonempty, single-line scalar")
    return value


@dataclass
class Document:
    path: Path
    fields: dict
    header: list
    body: str

    @classmethod
    def read(cls, path, scope, max_lines=None):
        try:
            if not path.is_file():
                raise ValueError("expected a regular memory file")
            with path.open(encoding="utf-8", newline="") as stream:
                lines = stream.read().splitlines(keepends=True)
            if max_lines is not None and len(lines) > max_lines:
                raise ValueError(f"{len(lines)} lines exceeds the {max_lines}-line limit")
            if not lines or lines[0].rstrip("\r\n") != "---":
                raise ValueError("missing YAML frontmatter")
            fields = {}
            for index, line in enumerate(lines[1:], start=1):
                if line.rstrip("\r\n") == "---":
                    break
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                match = re.fullmatch(r"([a-z][a-z0-9_]*):[ \t]+(.+)", line.rstrip("\r\n"))
                if match is None or match[1] in fields:
                    raise ValueError(f"invalid or duplicate frontmatter key on line {index + 1}")
                fields[match[1]] = yaml_scalar(match[2].strip())
            else:
                raise ValueError("unterminated YAML frontmatter")
            missing = (FIELDS[scope] | {"scope", "updated_at"}) - fields.keys()
            if missing:
                raise ValueError(f"missing frontmatter fields: {', '.join(sorted(missing))}")
            if fields["scope"] != scope:
                raise ValueError(f"expected scope {scope!r}, got {fields['scope']!r}")
            check_timestamp(fields["updated_at"])
        except (OSError, ValueError) as error:
            raise ValueError(f"{path}: {error}") from error
        return cls(path, fields, lines[:index + 1], "".join(lines[index + 1:]))

    def render(self, *, body=None, **updates):
        fields = {**self.fields, **updates, "updated_at": timestamp()}
        header = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items())
        return f"---\n{header}\n---\n" + (self.body if body is None else body)

    def revise(self, *, body=None, **updates):
        updates["updated_at"] = timestamp()
        header = []
        for line in self.header:
            key, _, _ = line.partition(":")
            if key in updates:
                ending = line[len(line.rstrip("\r\n")):]
                line = f"{key}: {json.dumps(updates[key], ensure_ascii=False)}{ending}"
            header.append(line)
        return "".join(header) + (self.body if body is None else body)


def table_row(values):
    cells = []
    for value in values:
        if value.strip() != value or value.splitlines() != [value]:
            raise ValueError("portfolio cells must fit on one line with no surrounding whitespace")
        cells.append(value.replace("\\", "\\\\").replace("|", r"\|"))
    return "| " + " | ".join(cells) + " |\n"


@dataclass
class Project:
    project_id: str
    workdirs: tuple
    memory_path: Path
    status: str
    priority: str
    summary: str
    blocker: str

    @classmethod
    def from_row(cls, row, root):
        cells = next(csv.reader([row], delimiter="|", escapechar="\\", quoting=csv.QUOTE_NONE, strict=True))
        if len(cells) != len(COLUMNS) + 2 or cells[0] != "" or cells[-1].strip():
            raise ValueError("expected one complete portfolio table row")
        slug, repo_paths, memory, status, priority, summary, blocker = map(str.strip, cells[1:-1])
        check_slug(slug)
        paths = json.loads(repo_paths)
        if not isinstance(paths, list) or not paths or not all(isinstance(path, str) for path in paths):
            raise ValueError("repo_paths must be a nonempty JSON array of absolute paths")
        workdirs = tuple(absolute(path).resolve() for path in paths)
        if any(path == root or path in root.parents for path in workdirs):
            raise ValueError("a project work directory cannot include the shared workspace root")
        memory_path = project_memory_path(memory, root)
        if status not in {"active", "paused"} or not all((priority, summary, blocker)):
            raise ValueError("expected an active or paused project with priority, summary and blocker")
        return cls(slug, workdirs, memory_path, status, priority, summary, blocker)

    def row(self):
        directories = json.dumps([str(path) for path in self.workdirs], ensure_ascii=False)
        return table_row((self.project_id, directories, str(self.memory_path), self.status,
                          self.priority, self.summary, self.blocker))

    def summary_dict(self):
        return {"project_id": self.project_id, "priority": self.priority,
                "summary": self.summary, "blocker": self.blocker}


class Portfolio:
    def __init__(self, path, root):
        self.document = Document.read(path, "portfolio", 120)
        if absolute(self.document.fields["workspace_root"]).resolve() != root:
            raise ValueError(f"{path}: workspace_root does not match {root}")
        self.lines = self.document.body.splitlines(keepends=True)
        header = table_row(COLUMNS).strip()
        headers = [i for i, line in enumerate(self.lines) if line.strip() == header]
        if len(headers) != 1:
            raise ValueError(f"{path}: expected one project registry table")
        first = headers[0] + 1
        separator = table_row(["---"] * len(COLUMNS)).strip()
        if first >= len(self.lines) or self.lines[first].strip() != separator:
            raise ValueError(f"{path}: invalid project registry separator")
        self.end = first + 1
        self.projects = {}
        memory_paths = set()
        workdirs = set()
        while self.end < len(self.lines) and self.lines[self.end].lstrip().startswith("|"):
            try:
                project = Project.from_row(self.lines[self.end].strip(), root)
                if project.project_id in self.projects:
                    raise ValueError(f"duplicate project_id {project.project_id!r}")
                if project.memory_path in memory_paths:
                    raise ValueError(f"duplicate memory_path {project.memory_path}")
                if len(set(project.workdirs)) != len(project.workdirs) or workdirs.intersection(project.workdirs):
                    raise ValueError(f"duplicate registered work directory for {project.project_id}")
            except (ValueError, csv.Error) as error:
                raise ValueError(f"{path}: {error}") from error
            self.projects[project.project_id] = (project, self.end)
            memory_paths.add(project.memory_path)
            workdirs.update(project.workdirs)
            self.end += 1

    def render(self, lines):
        content = self.document.revise(body="".join(lines))
        if len(content.splitlines()) > 120:
            raise ValueError("the portfolio would exceed 120 lines")
        return content

    def require_project(self, slug):
        check_slug(slug)
        if slug in self.projects:
            return self.projects[slug][0]
        if (self.document.path.parent / "archive" / slug / "MEMORY.md").is_file():
            raise ValueError(f"project is archived: {slug}")
        raise ValueError(f"project is not registered: {slug}")

    def checked_row(self, project, root):
        row = project.row()
        candidate = Project.from_row(row.strip(), root)
        workdirs = set(candidate.workdirs)
        if len(workdirs) != len(candidate.workdirs):
            raise ValueError(f"duplicate registered work directory for {candidate.project_id}")
        for existing, _ in self.projects.values():
            if existing.project_id == candidate.project_id:
                continue
            if existing.memory_path == candidate.memory_path or workdirs.intersection(existing.workdirs):
                raise ValueError(f"registration conflicts with {existing.project_id}")
        return row

    def add(self, project, root):
        if project.project_id in self.projects:
            raise ValueError(f"project already registered: {project.project_id}")
        lines = self.lines[:self.end]
        if not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        return self.render(lines + [self.checked_row(project, root)] + self.lines[self.end:])

    def update(self, project, root):
        _, index = self.projects[project.project_id]
        row = self.checked_row(project, root)
        original = self.lines[index]
        ending = original[len(original.rstrip("\r\n")):]
        return self.render(self.lines[:index] + [row.rstrip("\n") + ending] + self.lines[index + 1:])

    def remove(self, project_id):
        _, line = self.projects[project_id]
        return self.render(self.lines[:line] + self.lines[line + 1:])


def read_project(path, project_id, status, repo_path=None):
    document = Document.read(path, "project")
    fields = document.fields
    if fields["project_id"] != project_id or fields["status"] != status:
        raise ValueError(f"{path}: project_id or status disagrees with its registration")
    declared_repo = absolute(fields["repo_path"]).resolve()
    if repo_path is not None and declared_repo != repo_path:
        raise ValueError(f"{path}: repo_path must match the first registered work directory")
    ledger = path.with_name("ledger.jsonl")
    if absolute(fields["ledger_path"]).resolve() != ledger or not ledger.is_file() or ledger.is_symlink():
        raise ValueError(f"{path}: ledger_path must identify the adjacent ledger.jsonl")
    return document, ledger


def check_job_event(event, latest):
    if not isinstance(event, dict) or not all(
        isinstance(event.get(field), str) and event[field].strip() for field in JOB_FIELDS
    ):
        raise ValueError("missing or empty external job fields")
    if event["status"] not in JOB_STATUSES:
        raise ValueError(f"unknown job status {event['status']!r}")
    check_timestamp(event["submitted_at"])
    check_timestamp(event["verified_at"])
    job_key = event["platform"], event["job_id"]
    if job_key in latest and latest[job_key]["submitted_at"] != event["submitted_at"]:
        raise ValueError("a job's original submitted_at changed")
    return job_key


def read_job_events(stream, path):
    latest = {}
    needs_separator = False
    for number, line in enumerate(stream, start=1):
        try:
            event = json.loads(line)
            latest[check_job_event(event, latest)] = event
        except ValueError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
        needs_separator = not line.endswith("\n")
    return latest, needs_separator


def pending_jobs(path):
    with path.open(encoding="utf-8", newline="") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        latest, _ = read_job_events(stream, path)
    return [{field: event[field] for field in JOB_FIELDS}
            for event in latest.values() if event["status"] not in TERMINAL]


@contextmanager
def store_lock(directory, *, write):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
        yield
    finally:
        os.close(fd)


def atomic_write(path, content):
    path = path.resolve()
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def legacy_warning(root):
    path = root / "MEMORY.md"
    if path.exists() or path.is_symlink():
        return f"unclassified legacy memory at {path}; move it out of the shared root"
    return None


def init_workspace(root, directory):
    templates = [(name, scope, Document.read(TEMPLATES / name, scope)) for name, scope in
                 (("SELF.md", "self"), ("PORTFOLIO.md", "portfolio"))]
    directory.mkdir(mode=0o700)
    try:
        for name, scope, template in templates:
            fields = {"workspace_root": str(root)} if scope == "portfolio" else {}
            atomic_write(directory / name, template.render(**fields))
    except (OSError, ValueError):
        shutil.rmtree(directory)
        raise


def publish_project(folder, memory, ledger_source, portfolio, registry):
    folder.parent.mkdir(mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    try:
        atomic_write(folder / "MEMORY.md", memory)
        # Stream the original bytes, including archived or empty ledgers.
        ledger = folder / "ledger.jsonl"
        with ledger_source.open("rb") as source, ledger.open("xb") as destination:
            os.fchmod(destination.fileno(), 0o600)
            shutil.copyfileobj(source, destination)
        atomic_write(portfolio.document.path, registry)
    except (OSError, ValueError):
        shutil.rmtree(folder)
        raise


def init_project(root, directory, portfolio, args):
    check_slug(args.slug)
    folder = (directory / "projects").resolve() / args.slug
    archived = directory / "archive" / args.slug
    if archived.exists() or archived.is_symlink():
        raise ValueError(f"project is already archived: {archived}")
    if args.repo_path:
        workdirs = tuple(path.resolve(strict=True) for path in args.repo_path)
    else:
        cwd = Path.cwd().resolve()
        workdirs = (folder if cwd == root else cwd,)
    if any(path != folder and not path.is_dir() for path in workdirs):
        raise ValueError("project work directories must be directories")
    project = Project(args.slug, workdirs, project_memory_path(folder / "MEMORY.md", root), "active",
                      args.priority, args.summary, args.blocker)
    registry = portfolio.add(project, root)
    template = Document.read(TEMPLATES / "PROJECT_MEMORY.md", "project")
    memory = template.render(project_id=args.slug, repo_path=str(workdirs[0]), ledger_path=str(folder / "ledger.jsonl"))
    publish_project(folder, memory, TEMPLATES / "ledger.jsonl", portfolio, registry)


def append_job(portfolio, args):
    project = portfolio.require_project(args.slug)
    _, ledger = read_project(project.memory_path, project.project_id, project.status, project.workdirs[0])
    event = {field: getattr(args, field) for field in JOB_FIELDS}
    if args.source_ledger is not None:
        if not args.source_ledger.strip():
            raise ValueError("source_ledger must be nonempty")
        event["source_ledger"] = args.source_ledger

    with ledger.open("ab", buffering=0) as destination:
        fcntl.flock(destination.fileno(), fcntl.LOCK_EX)
        with ledger.open(encoding="utf-8", newline="") as history:
            latest, needs_separator = read_job_events(history, ledger)
        now = timestamp()
        previous = latest.get((args.platform, args.job_id))
        if args.submitted_at is None:
            event["submitted_at"] = previous["submitted_at"] if previous else now
        if args.verified_at is None:
            event["verified_at"] = now
        check_job_event(event, latest)

        separator = "\n" if needs_separator else ""
        payload = (separator + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        original_size = os.fstat(destination.fileno()).st_size
        try:
            if destination.write(payload) != len(payload):
                raise OSError(f"{ledger}: incomplete job event write")
            destination.flush()
            os.fsync(destination.fileno())
        except OSError:
            destination.truncate(original_size)
            raise


def update_project(root, portfolio, args):
    fields = {name: getattr(args, name) for name in ("status", "priority", "summary", "blocker")
              if getattr(args, name) is not None}
    if not fields and args.add_repo_path is None and args.remove_repo_path is None:
        raise ValueError("update-project requires at least one field or work directory change")

    project = portfolio.require_project(args.slug)
    workdirs = list(project.workdirs)
    if args.remove_repo_path is not None:
        path = absolute(args.remove_repo_path).resolve()
        if path not in workdirs:
            raise ValueError(f"work directory is not registered for {args.slug}: {path}")
        workdirs.remove(path)
    if args.add_repo_path is not None:
        path = absolute(args.add_repo_path).resolve(strict=True)
        if not path.is_dir():
            raise ValueError(f"expected a work directory, got {path}")
        workdirs.append(path)
    if not workdirs:
        raise ValueError("cannot remove the last work directory")

    updated = replace(project, workdirs=tuple(workdirs), **fields)
    registry = portfolio.update(updated, root)
    metadata = {}
    if updated.status != project.status:
        metadata["status"] = updated.status
    if updated.workdirs[0] != project.workdirs[0]:
        metadata["repo_path"] = str(updated.workdirs[0])
    if not metadata:
        atomic_write(portfolio.document.path, registry)
        return

    document, _ = read_project(project.memory_path, project.project_id, project.status, project.workdirs[0])
    atomic_write(document.path, document.revise(**metadata))
    try:
        atomic_write(portfolio.document.path, registry)
    except (OSError, ValueError):
        atomic_write(document.path, "".join(document.header) + document.body)
        raise


def archive_project(root, directory, portfolio, slug):
    project = portfolio.require_project(slug)
    document, ledger = read_project(project.memory_path, slug, project.status, project.workdirs[0])
    pending_jobs(ledger)
    folder = (directory / "archive").resolve() / slug
    project_memory_path(folder / "MEMORY.md", root)
    memory = document.render(status="archived", ledger_path=str(folder / "ledger.jsonl"))
    publish_project(folder, memory, ledger, portfolio, portfolio.remove(slug))
    # The registry now points readers away from the old pair. Both files already exist in the archive.
    for source in (project.memory_path, ledger):
        try:
            source.unlink()
        except OSError as error:
            raise ValueError(f"archived at {folder}; original cleanup pending at {source}: {error}") from error


def route(root, portfolio, args):
    cwd = Path.cwd().resolve()
    warning = legacy_warning(root)
    projects = [project for project, _ in portfolio.projects.values()]
    matching = [(len(path.parts), project) for project in projects if project.status == "active"
                for path in project.workdirs if cwd == path or path in cwd.parents]
    selected = max(matching, key=lambda candidate: candidate[0])[1] if matching else None
    if args.project:
        if args.project not in portfolio.projects:
            raise ValueError(f"project is not registered: {args.project}")
        if selected and selected.project_id != args.project:
            raise ValueError(f"current directory belongs to {selected.project_id!r}, not {args.project!r}")
        selected, _ = portfolio.projects[args.project]
    warnings = [warning] if warning else []
    if not selected:
        return {"selection": "choose", "active_projects": [project.summary_dict() for project in projects
                                                          if project.status == "active"], "warnings": warnings}
    _, ledger = read_project(selected.memory_path, selected.project_id, selected.status, selected.workdirs[0])
    return {"selection": "selected", **selected.summary_dict(), "memory_path": str(selected.memory_path),
            "ledger_path": str(ledger), "pending_jobs": pending_jobs(ledger), "warnings": warnings}


def validate(root, directory):
    errors = []
    warnings = []
    warning = legacy_warning(root)
    if warning:
        errors.append(warning)
    try:
        Document.read(directory / "SELF.md", "self", 50)
    except ValueError as error:
        errors.append(str(error))
    try:
        portfolio = Portfolio(directory / "PORTFOLIO.md", root)
    except ValueError as error:
        errors.append(str(error))
        return errors, warnings
    project_paths = set()
    candidates = []
    for project, _ in portfolio.projects.values():
        project_paths.add(project.memory_path)
        candidates.append((project.memory_path, project.project_id, project.status, project.workdirs[0]))
    for path in (directory / "projects").glob("*/MEMORY.md"):
        if path.resolve() not in project_paths:
            errors.append(f"unregistered project memory at {path}")
    for folder in (directory / "archive").glob("*"):
        if folder.is_dir():
            if folder.name in portfolio.projects:
                errors.append(f"archived project {folder.name!r} still appears in the registry")
            candidates.append((folder / "MEMORY.md", folder.name, "archived", None))
    for path, slug, status, workdir in candidates:
        try:
            check_slug(slug)
            path = project_memory_path(path, root)
            document, ledger = read_project(path, slug, status, workdir)
            line_count = len(document.header) + len(document.body.splitlines())
            if status != "archived" and line_count > PROJECT_LINE_BUDGET:
                warnings.append(f"project {slug!r} at {path} has {line_count} lines (over {PROJECT_LINE_BUDGET}). "
                                "Save a dated private snapshot, then consider condensing it.")
            pending_jobs(ledger)
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd(), help="explicit shared workspace root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-workspace", help="initialize a private L0 and L1")
    commands.add_parser("validate", help="validate the registry, project memories and archives")
    route_parser = commands.add_parser("route", help="select and inspect at most one project")
    route_parser.add_argument("--project", help="explicit project_id from the registry")
    init_parser = commands.add_parser("init-project", help="create and register a project")
    init_parser.add_argument("slug")
    init_parser.add_argument("--repo-path", type=Path, action="append", help="work directory, repeat for aliases")
    init_parser.add_argument("--priority", default="unset")
    init_parser.add_argument("--summary", default="Registered")
    init_parser.add_argument("--blocker", default="-")
    job_parser = commands.add_parser("append-job", help="append a verified external job event")
    job_parser.add_argument("slug", metavar="project_id")
    for field in ("job-id", "platform", "purpose", "cost-risk", "status-query"):
        job_parser.add_argument(f"--{field}", required=True)
    job_parser.add_argument("--status", choices=sorted(JOB_STATUSES), required=True)
    job_parser.add_argument("--submitted-at")
    job_parser.add_argument("--verified-at")
    job_parser.add_argument("--source-ledger")
    update_parser = commands.add_parser("update-project", help="update a registered project")
    update_parser.add_argument("slug", metavar="project_id")
    update_parser.add_argument("--status", choices=("active", "paused"))
    update_parser.add_argument("--priority")
    update_parser.add_argument("--summary")
    update_parser.add_argument("--blocker")
    update_parser.add_argument("--add-repo-path", type=Path)
    update_parser.add_argument("--remove-repo-path", type=Path)
    commands.add_parser("archive", help="move project memory and ledger into the archive").add_argument("slug")
    args = parser.parse_args()
    try:
        root = args.workspace_root.resolve(strict=True)
        directory = root / ".agent-memory"
        if args.command == "init-workspace":
            init_workspace(root, directory)
            return 0
        directory = directory.resolve(strict=True)
        with store_lock(directory, write=args.command in {"init-project", "update-project", "archive"}):
            if args.command == "validate":
                errors, warnings = validate(root, directory)
                for warning in warnings:
                    print(f"warning: {warning}", file=sys.stderr)
                for error in errors:
                    print(f"error: {error}", file=sys.stderr)
                if errors:
                    return 1
                print("Memory store is valid.")
                return 0
            Document.read(directory / "SELF.md", "self", 50)
            portfolio = Portfolio(directory / "PORTFOLIO.md", root)
            if args.command == "route":
                print(json.dumps(route(root, portfolio, args), ensure_ascii=False))
            elif args.command == "init-project":
                init_project(root, directory, portfolio, args)
            elif args.command == "append-job":
                append_job(portfolio, args)
            elif args.command == "update-project":
                update_project(root, portfolio, args)
            else:
                archive_project(root, directory, portfolio, args.slug)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"memory_ctl: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
