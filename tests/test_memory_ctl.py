import json
import runpy
import shlex
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


CLI = Path(__file__).resolve().parents[1] / "scripts" / "memory_ctl.py"
TRACE_OPEN = """
import os, runpy, sys
root, script, *arguments = sys.argv[1:]
def observe(event, args):
    if event == 'open' and isinstance(args[0], str):
        path = os.path.abspath(args[0])
        if path.startswith(root + os.sep) and path.endswith(('.md', '.jsonl')):
            print('open', path, file=sys.stderr)
sys.addaudithook(observe)
sys.argv = [script, *arguments]
runpy.run_path(script, run_name='__main__')
"""


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.store = self.root / ".agent-memory"
        self.portfolio = self.store / "PORTFOLIO.md"
        self.self_path = self.store / "SELF.md"
        self.command("init-workspace")

    def cli(self, traced=False):
        prefix = ["-c", TRACE_OPEN, str(self.root)] if traced else []
        return [sys.executable, *prefix, str(CLI), "--workspace-root", str(self.root)]

    def run_command(self, arguments, *, cwd=None, traced=False):
        return subprocess.run(self.cli(traced) + list(arguments), cwd=cwd or self.root,
                              capture_output=True, text=True, check=False, timeout=10)

    def command(self, *arguments, cwd=None, code=0, traced=False):
        result = self.run_command(arguments, cwd=cwd, traced=traced)
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def register(self, slug, *names, priority="unset"):
        arguments = []
        for name in names:
            path = self.root / name
            path.mkdir(parents=True)
            arguments.extend(["--repo-path", str(path)])
        self.command("init-project", slug, "--priority", priority, *arguments)
        return self.store / "projects" / slug

    def opens(self, result):
        return [Path(line.removeprefix("open ")) for line in result.stderr.splitlines() if line.startswith("open ")]

    def event(self, job_id, status, query):
        return {"job_id": job_id, "platform": "fixture", "purpose": "recovery test",
                "submitted_at": "2026-01-01T00:00:00Z", "cost_risk": "none",
                "status_query": query, "status": status, "verified_at": "2026-01-01T00:00:00Z"}

    def append_args(self, status="submitted", *, platform="fixture", purpose="recovery test"):
        return ("append-job", "alpha", "--job-id", "job-1", "--platform", platform, "--purpose", purpose,
                "--cost-risk", "none", "--status-query", r"cat '/tmp/status|job\1'", "--status", status)

    def test_t1_shared_root_ambiguous_opens_only_resident_layers(self):
        self.register("alpha", "alpha", priority="high")
        self.register("beta", "beta", priority="low")
        result = self.command("route", traced=True)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["selection"], "choose")
        self.assertEqual([(entry["project_id"], entry["priority"]) for entry in decision["active_projects"]],
                         [("alpha", "high"), ("beta", "low")])
        self.assertEqual(self.opens(result), [self.self_path, self.portfolio])

    def test_t2_named_project_opens_only_its_l2_and_can_recheck_git(self):
        project = self.register("alpha", "alpha")
        self.register("beta", "beta")
        repo = self.root / "alpha"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgSign=false", "commit", "-qm", "Fixture revision", "--allow-empty"], check=True)
        result = self.command("route", "--project", "alpha", traced=True)
        decision = json.loads(result.stdout)
        expected = [project / "MEMORY.md", project / "ledger.jsonl"]
        self.assertEqual(decision["project_id"], "alpha")
        self.assertEqual(Path(decision["memory_path"]), expected[0])
        self.assertEqual(self.opens(result), [self.self_path, self.portfolio, *expected])
        self.assertEqual(subprocess.check_output(["git", "-C", str(repo), "status", "--short"], text=True), "")
        self.assertEqual(subprocess.check_output(["git", "-C", str(repo), "log", "-1", "--format=%s"], text=True).strip(),
                         "Fixture revision")

    def test_t3_worktree_auto_routes_without_prefix_guessing(self):
        project = self.register("alpha", "alpha", "alpha-repair | sandbox")
        nested = self.root / "alpha-repair | sandbox" / "src"
        nested.mkdir()
        self.register("beta", "alphabet")
        result = self.command("route", cwd=nested, traced=True)
        self.assertEqual(json.loads(result.stdout)["memory_path"], str(project / "MEMORY.md"))
        nearby = self.root / "alpha-unregistered"
        nearby.mkdir()
        self.assertEqual(json.loads(self.command("route", cwd=nearby).stdout)["selection"], "choose")
        result = self.command("route", "--project", "beta", cwd=nested, code=1, traced=True)
        self.assertIn("current directory belongs to 'alpha'", result.stderr)
        self.assertEqual(self.opens(result), [self.self_path, self.portfolio])

    def test_t4_shared_root_legacy_memory_is_detected_and_never_opened(self):
        self.register("alpha", "alpha")
        stray = self.root / "MEMORY.md"
        stray.write_bytes(b"\xffunclassified\n")
        result = self.command("validate", code=1, traced=True)
        self.assertIn("unclassified legacy memory", result.stderr)
        self.assertNotIn(stray, self.opens(result))
        result = self.command("route", traced=True)
        self.assertEqual(json.loads(result.stdout)["selection"], "choose")
        self.assertIn(str(stray), json.loads(result.stdout)["warnings"][0])
        self.assertEqual(self.opens(result), [self.self_path, self.portfolio])
        stray.unlink()
        stray.symlink_to(self.root / "missing")
        self.assertIn("unclassified legacy memory", self.command("validate", code=1).stderr)

    def test_t5_recovery_keeps_original_job_id_and_reads_provider_status(self):
        project = self.register("alpha", "alpha")
        status = self.root / "fixture-job-7.status"
        status.write_text("fixture-job-7 running\n", encoding="utf-8")
        ledger = project / "ledger.jsonl"
        query = shlex.join(["cat", str(status)])
        submitted = self.event("fixture-job-7", "submitted", query)
        running = self.event("fixture-job-7", "running", query)
        finished = self.event("fixture-job-6", "failed", query)
        original = "".join(json.dumps(event) + "\n" for event in [submitted, running, finished])
        ledger.write_text(original, encoding="utf-8")
        self.assertEqual(json.loads(self.command("route", "--project", "alpha").stdout)["pending_jobs"], [running])
        recovered = json.loads(self.command("route", "--project", "alpha").stdout)["pending_jobs"]
        self.assertEqual(subprocess.check_output(shlex.split(recovered[0]["status_query"]), text=True).strip(),
                         "fixture-job-7 running")
        self.assertEqual(ledger.read_text(encoding="utf-8"), original)

    def test_t6_l2_progress_then_archive_preserves_ledger_and_line_limits(self):
        project = self.register("alpha", "alpha")
        memory = project / "MEMORY.md"
        ledger = project / "ledger.jsonl"
        registry = self.portfolio.read_bytes()
        with memory.open("a", encoding="utf-8") as stream:
            stream.write("\n- Verified the project's fixture.\n")
        history = json.dumps(self.event("job-1", "succeeded", "cat /tmp/fixture")) + "\n"
        ledger.write_text(history, encoding="utf-8")
        self.command("validate")
        self.assertEqual(self.portfolio.read_bytes(), registry)
        self.command("archive", "alpha")
        archived = self.store / "archive" / "alpha"
        archived_memory = (archived / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn('status: "archived"', archived_memory)
        self.assertIn("Verified the project's fixture", archived_memory)
        self.assertEqual((archived / "ledger.jsonl").read_bytes(), history.encode())
        self.assertFalse(memory.exists())
        self.assertFalse(ledger.exists())
        self.assertEqual(json.loads(self.command("route").stdout)["active_projects"], [])
        self.assertLessEqual(len(self.self_path.read_text().splitlines()), 50)
        self.assertLessEqual(len(self.portfolio.read_text().splitlines()), 120)
        self.command("validate")

    def test_invalid_frontmatter_and_duplicate_mapped_path_fail_validation(self):
        project = self.register("alpha", "alpha")
        self.register("beta", "beta")
        with self.self_path.open("a", encoding="utf-8") as stream:
            stream.write("row\n" * 50)
        self.portfolio.write_text(self.portfolio.read_text().replace(
            str(self.store / "projects/beta/MEMORY.md"), str(project / "MEMORY.md")))
        result = self.command("validate", code=1)
        self.assertIn("50-line limit", result.stderr)
        self.assertIn("duplicate memory_path", result.stderr)

    def test_scope_mismatch_and_malformed_job_events_fail_selection(self):
        project = self.register("alpha", "alpha")
        memory = project / "MEMORY.md"
        original = memory.read_text(encoding="utf-8")
        memory.write_text(original.replace('scope: "project"', 'scope: "self"'), encoding="utf-8")
        self.assertIn("expected scope 'project'", self.command("route", "--project", "alpha", code=1).stderr)
        memory.write_text(original, encoding="utf-8")
        (project / "ledger.jsonl").write_text('{"job_id":"incomplete"}\n', encoding="utf-8")
        self.assertIn("missing or empty external job fields", self.command("validate", code=1).stderr)

    def test_concurrent_registrations_keep_both_rows(self):
        commands = [self.cli() + ["init-project", name] for name in ("one", "two")]
        workers = [subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                   for command in commands]
        for worker in workers:
            _, stderr = worker.communicate(timeout=10)
            self.assertEqual(worker.returncode, 0, stderr)
        ids = {entry["project_id"] for entry in json.loads(self.command("route").stdout)["active_projects"]}
        self.assertEqual(ids, {"one", "two"})
        self.command("validate")

    def test_archive_destination_conflict_keeps_the_original_pair_and_row(self):
        project = self.register("alpha", "alpha")
        (self.store / "archive" / "alpha").mkdir(parents=True)
        original = self.portfolio.read_bytes()
        self.command("archive", "alpha", code=1)
        self.assertEqual(original, self.portfolio.read_bytes())
        self.assertTrue((project / "MEMORY.md").is_file())
        self.assertTrue((project / "ledger.jsonl").is_file())

    def test_append_job_writes_compact_utf8_and_inherits_submission_time(self):
        ledger = self.register("alpha", "alpha") / "ledger.jsonl"
        submitted_at = "2026-01-01T00:00:00.123+00:00"
        purpose = "\u6e32\u67d3\nverification"
        self.command(*self.append_args(purpose=purpose), "--submitted-at", submitted_at,
                     "--source-ledger", "provider:original")
        history = ledger.read_bytes()
        first = json.loads(history)
        self.assertEqual(first["submitted_at"], submitted_at)
        self.assertRegex(first["verified_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(first["purpose"], purpose)
        self.assertEqual(first["status_query"], r"cat '/tmp/status|job\1'")
        self.assertEqual(first["source_ledger"], "provider:original")
        self.assertEqual(history, (json.dumps(first, ensure_ascii=False, separators=(",", ":")) + "\n").encode())

        verified_at = "2026-01-02T10:30:00Z"
        self.command(*self.append_args("running"), "--verified-at", verified_at)
        self.command(*self.append_args(platform="other-platform"))
        contents = ledger.read_bytes()
        self.assertTrue(contents.startswith(history))
        running, other = map(json.loads, contents[len(history):].splitlines())
        self.assertEqual((running["status"], running["submitted_at"], running["verified_at"]),
                         ("running", submitted_at, verified_at))
        self.assertEqual(other["submitted_at"], other["verified_at"])
        self.assertEqual(other["platform"], "other-platform")
        self.command("validate")

    def test_append_job_rejects_invalid_events_without_changing_history(self):
        ledger = self.register("alpha", "alpha") / "ledger.jsonl"
        self.command(*self.append_args(), "--submitted-at", "2026-01-01T00:00:00Z")
        history = ledger.read_bytes()
        cases = [
            (self.append_args("running") + ("--submitted-at", "2026-01-02T00:00:00Z"), 1, "original submitted_at"),
            (self.append_args("invalid"), 2, "invalid choice"),
            (self.append_args("running") + ("--verified-at", "2026-01-01T00:00:00+01:00"), 1, "UTC timestamp"),
            (self.append_args(purpose=" "), 1, "empty external job fields"),
        ]
        for arguments, code, message in cases:
            with self.subTest(message=message):
                self.assertIn(message, self.command(*arguments, code=code).stderr)
                self.assertEqual(ledger.read_bytes(), history)

    def test_append_job_preserves_unterminated_history_and_rejects_archived_project(self):
        ledger = self.register("alpha", "alpha") / "ledger.jsonl"
        original = json.dumps(self.event("job-1", "submitted", "cat /tmp/fixture")).encode()
        ledger.write_bytes(original)
        self.command(*self.append_args("running"))
        history = ledger.read_bytes()
        self.assertTrue(history.startswith(original + b"\n"))
        self.assertEqual(json.loads(history.splitlines()[1])["submitted_at"], "2026-01-01T00:00:00Z")
        self.command("archive", "alpha")
        result = self.command(*self.append_args("failed"), code=1)
        self.assertIn("project is archived", result.stderr)
        self.assertEqual((self.store / "archive" / "alpha" / "ledger.jsonl").read_bytes(), history)

    def test_concurrent_appends_agree_on_job_identity(self):
        ledger = self.register("alpha", "alpha") / "ledger.jsonl"
        first = self.append_args() + ("--submitted-at", "2026-01-01T00:00:00Z")
        second = self.append_args() + ("--submitted-at", "2026-01-02T00:00:00Z")
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(self.run_command, (first, second)))
        self.assertEqual(sorted(result.returncode for result in results), [0, 1])
        self.assertIn("original submitted_at", next(result.stderr for result in results if result.returncode))
        self.assertEqual(len(ledger.read_bytes().splitlines()), 1)
        self.command("validate")

    def test_update_project_only_changes_its_row_and_timestamp(self):
        memory = self.register("alpha", "alpha") / "MEMORY.md"
        self.register("beta", "beta")
        original_memory = memory.read_bytes()
        original_rows = self.portfolio.read_bytes().splitlines()
        timestamp_line = next(i for i, row in enumerate(original_rows) if row.startswith(b"updated_at:"))
        original_rows[timestamp_line] = b"updated_at: 2026-01-01T00:00:00Z"
        self.portfolio.write_bytes(b"\r\n".join(original_rows) + b"\r\n")
        summary = r"Release | review\smoke"
        blocker = r"Test\gate | waiting"

        self.command("update-project", "alpha", "--summary", summary, "--blocker", blocker)
        decision = json.loads(self.command("route", "--project", "alpha").stdout)
        self.assertEqual((decision["summary"], decision["blocker"]), (summary, blocker))
        self.assertEqual(memory.read_bytes(), original_memory)
        rows = self.portfolio.read_bytes().split(b"\r\n")
        self.assertEqual(len(rows), len(original_rows) + 1)
        changed = [i for i, (old, new) in enumerate(zip(original_rows, rows)) if old != new]
        alpha_line = next(i for i, row in enumerate(original_rows) if row.startswith(b"| alpha |"))
        self.assertEqual(changed, [timestamp_line, alpha_line])
        self.assertIn(rb"Release \| review\\smoke", rows[alpha_line])
        self.assertIn(rb"Test\\gate \| waiting", rows[alpha_line])

    def test_update_project_syncs_pause_resume_and_primary_directory(self):
        memory = self.register("alpha", "alpha", "secondary") / "MEMORY.md"
        original = memory.read_text()
        self.command("update-project", "alpha", "--status", "paused",
                     "--remove-repo-path", str(self.root / "alpha"))
        paused = memory.read_text()
        self.assertIn('status: "paused"', paused)
        self.assertIn(f'repo_path: "{self.root / "secondary"}"', paused)
        self.assertEqual(paused.split("\n---\n", 1)[1], original.split("\n---\n", 1)[1])
        self.assertEqual(json.loads(self.command("route", cwd=self.root / "secondary").stdout)["selection"], "choose")
        self.assertEqual(json.loads(self.command("route", "--project", "alpha").stdout)["selection"], "selected")
        self.command("validate")

        workdir = self.root / "next-worktree"
        workdir.mkdir()
        self.command("update-project", "alpha", "--status", "active", "--add-repo-path", str(workdir),
                     "--remove-repo-path", str(self.root / "secondary"))
        self.assertIn('status: "active"', memory.read_text())
        self.assertIn(f'repo_path: "{workdir}"', memory.read_text())
        self.assertEqual(json.loads(self.command("route", cwd=workdir).stdout)["project_id"], "alpha")
        self.command("validate")

    def test_update_project_rejects_invalid_status_and_paths(self):
        memory = self.register("alpha", "alpha") / "MEMORY.md"
        self.register("beta", "beta")
        alias = self.root / "beta-alias"
        alias.symlink_to(self.root / "beta", target_is_directory=True)
        before = self.portfolio.read_bytes(), memory.read_bytes()
        cases = [
            ((), 1, "at least one"),
            (("--status", "archived"), 2, "invalid choice"),
            (("--add-repo-path", str(alias)), 1, "registration conflicts with beta"),
            (("--add-repo-path", "beta"), 1, "expected an absolute path"),
            (("--add-repo-path", str(self.root / "absent")), 1, "No such file or directory"),
            (("--remove-repo-path", str(self.root / "alpha")), 1, "last work directory"),
        ]
        for options, code, message in cases:
            with self.subTest(options=options):
                self.assertIn(message, self.command("update-project", "alpha", *options, code=code).stderr)
                self.assertEqual((self.portfolio.read_bytes(), memory.read_bytes()), before)

    def test_concurrent_project_updates_keep_both_rows_and_fields(self):
        self.register("alpha", "alpha")
        self.register("beta", "beta")
        commands = [
            ("update-project", "alpha", "--priority", "high"),
            ("update-project", "alpha", "--summary", "Reviewed"),
            ("update-project", "beta", "--blocker", "Awaiting data"),
        ]
        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(self.run_command, commands))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        entries = {entry["project_id"]: entry for entry in json.loads(self.command("route").stdout)["active_projects"]}
        self.assertEqual((entries["alpha"]["priority"], entries["alpha"]["summary"]), ("high", "Reviewed"))
        self.assertEqual(entries["beta"]["blocker"], "Awaiting data")
        self.command("validate")

    def test_update_project_restores_memory_if_registry_write_fails(self):
        memory = self.register("alpha", "alpha") / "MEMORY.md"
        before = self.portfolio.read_bytes(), memory.read_bytes()
        main = runpy.run_path(str(CLI))["main"]
        atomic_write = main.__globals__["atomic_write"]

        def fail_portfolio_write(path, content):
            if path == self.portfolio:
                raise OSError("fixture registry write failure")
            atomic_write(path, content)

        argv = [str(CLI), "--workspace-root", str(self.root), "update-project", "alpha", "--status", "paused"]
        with patch.object(sys, "argv", argv), patch.dict(main.__globals__, atomic_write=fail_portfolio_write):
            with patch("sys.stderr") as stderr:
                self.assertEqual(main(), 1)
                stderr.write.assert_any_call("memory_ctl: fixture registry write failure")
        self.assertEqual((self.portfolio.read_bytes(), memory.read_bytes()), before)
        self.command("validate")

    def test_validate_l2_line_warning_is_nonblocking_and_keeps_hard_error_exit(self):
        project = self.register("alpha", "alpha")
        memory = project / "MEMORY.md"
        lines = len(memory.read_text().splitlines())
        with memory.open("a", encoding="utf-8") as stream:
            stream.write("line\n" * (150 - lines))
        self.assertEqual(self.command("validate").stderr, "")
        with memory.open("a", encoding="utf-8") as stream:
            stream.write("one more line\n")

        warning = self.command("validate").stderr
        self.assertIn(f"warning: project 'alpha' at {memory} has 151 lines", warning)
        self.assertIn("Save a dated private snapshot", warning)
        self.command("update-project", "alpha", "--status", "paused")
        self.assertEqual(self.command("validate").stderr, warning)
        ledger = project / "ledger.jsonl"
        ledger.write_text('{"job_id":"incomplete"}\n', encoding="utf-8")
        result = self.command("validate", code=1)
        self.assertIn(warning, result.stderr)
        self.assertIn(f"error: {ledger}:1: missing or empty external job fields", result.stderr)
        ledger.write_text("", encoding="utf-8")
        self.command("archive", "alpha")
        self.assertEqual(self.command("validate").stderr, "")


if __name__ == "__main__":
    unittest.main()
