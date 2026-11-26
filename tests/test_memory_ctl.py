import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

    def command(self, *arguments, cwd=None, code=0, traced=False):
        result = subprocess.run(self.cli(traced) + list(arguments), cwd=cwd or self.root,
                                capture_output=True, text=True, check=False)
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


if __name__ == "__main__":
    unittest.main()
