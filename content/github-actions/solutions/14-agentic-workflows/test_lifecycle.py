"""Offline regression checks. Requires the existing Flask test dependencies."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[3]
spec = importlib.util.spec_from_file_location("pets_lifecycle", STAGE / "lifecycle.py")
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class WorkflowContractTests(unittest.TestCase):
    def test_downstream_rerun_uses_producer_artifact_id(self):
        workflow = (STAGE / "agentic-safe.yml").read_text()
        producer, consumer = workflow.split("  human-audit:", 1)
        self.assertIn("artifact-id: ${{ steps.upload.outputs.artifact-id }}", producer)
        self.assertIn("        id: upload\n", producer)
        self.assertIn("name: pets-agentic-audit-${{ github.run_id }}-${{ github.run_attempt }}", producer)
        self.assertNotIn("github.run_attempt", consumer)
        download = consumer.split("uses: actions/download-artifact@", 1)[1].split("\n      - ", 1)[0]
        self.assertIn("artifact-ids: ${{ needs.simulate.outputs.artifact-id }}", download)
        self.assertIn("merge-multiple: true", download)
        self.assertNotIn("name:", download)

    def test_missing_id_cannot_fall_back_to_downloading_all_artifacts(self):
        workflow = (STAGE / "agentic-safe.yml").read_text()
        consumer = workflow.split("  human-audit:", 1)[1]
        guard, _ = consumer.split("uses: actions/download-artifact@", 1)
        self.assertIn("AUDIT_ARTIFACT_ID: ${{ needs.simulate.outputs.artifact-id }}", guard)
        self.assertIn('[[ "$AUDIT_ARTIFACT_ID" =~ ^[0-9]+$ ]]', guard)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.scratch = STAGE / ".validation" / uuid.uuid4().hex
        self.checkout = self.scratch / "checkout"
        self.work = self.scratch / "work"
        self.scratch.mkdir(parents=True)
        subprocess.run(
            ["git", "clone", "--quiet", "--shared", "--no-hardlinks",
             str(ROOT), str(self.checkout)], check=True, timeout=30,
        )
        self.sha = lifecycle.git(self.checkout, "rev-parse", "HEAD").decode().strip()
        self.goal = patch.dict(os.environ, {"UNTRUSTED_GOAL": "Explain dog-list tests"})
        self.goal.start()

    def tearDown(self):
        self.goal.stop()
        shutil.rmtree(self.scratch)
        if not any((STAGE / ".validation").iterdir()):
            (STAGE / ".validation").rmdir()

    def simulate(self):
        return lifecycle.simulate(self.checkout, self.work, Path(sys.executable))

    def test_real_pets_tests_and_transfer_equivalent_audit(self):
        self.assertEqual(self.simulate(), 0)
        copied = self.scratch / "download"
        shutil.copytree(self.work / "audit", copied)
        lifecycle.verify_audit(copied, self.sha)
        self.assertTrue(lifecycle.is_clean(self.checkout))
        self.assertFalse(list((self.work / "context").rglob("*.db")))
        self.assertFalse(list((self.work / "context").rglob("__pycache__")))

    def test_goal_is_inert(self):
        os.environ["UNTRUSTED_GOAL"] = '$(touch PWNED); `echo bad`\n${{ github.token }}'
        self.assertEqual(self.simulate(), 0)
        plan = json.loads((self.work / "audit/plan.json").read_text())
        self.assertEqual(plan["goal"], os.environ["UNTRUSTED_GOAL"])
        self.assertFalse(list(self.scratch.rglob("PWNED")))

    def test_oversized_goal_never_runs_tests(self):
        os.environ["UNTRUSTED_GOAL"] = "x" * 201
        with patch.object(lifecycle, "run_action") as action:
            self.assertNotEqual(self.simulate(), 0)
            action.assert_not_called()

    def test_200_character_goal_is_accepted(self):
        os.environ["UNTRUSTED_GOAL"] = "x" * 200
        self.assertEqual(self.simulate(), 0)
        lifecycle.verify_audit(self.work / "audit", self.sha)

    def test_empty_goal_never_runs_tests(self):
        os.environ["UNTRUSTED_GOAL"] = ""
        with patch.object(lifecycle, "run_action") as action:
            self.assertNotEqual(self.simulate(), 0)
            action.assert_not_called()

    def test_dirty_tracked_untracked_and_ignored_paths(self):
        for relative in ("app/server/app.py", "unexpected.txt", "node_modules/unexpected.txt"):
            with self.subTest(relative=relative):
                target = self.checkout / relative
                original = target.read_bytes() if target.exists() else None
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# unexpected change\n")
                with patch.object(lifecycle, "run_action") as action:
                    self.assertNotEqual(self.simulate(), 0)
                    action.assert_not_called()
                if original is None:
                    target.unlink()
                else:
                    target.write_bytes(original)
                shutil.rmtree(self.work)

    def test_post_action_ignored_write_rejected(self):
        original = lifecycle.run_action

        def dirty(*args):
            code = original(*args)
            target = self.checkout / "node_modules/unexpected.txt"
            target.parent.mkdir(exist_ok=True)
            target.write_text("unexpected\n")
            return code

        with patch.object(lifecycle, "run_action", side_effect=dirty):
            self.assertNotEqual(self.simulate(), 0)
        verdict = json.loads((self.work / "audit/verdict.json").read_text())
        self.assertFalse(verdict["checkout_clean"])

    def test_failing_api_assertion_keeps_nonzero_exit_and_log(self):
        original = lifecycle.run_action

        def failing(python, context, result, observation):
            with (context / "test_app.py").open("a") as stream:
                stream.write(
                    "\nclass DeliberateFailure(unittest.TestCase):\n"
                    "    def test_break(self):\n"
                    "        self.assertEqual(200, 500)\n"
                )
            return original(python, context, result, observation)

        with patch.object(lifecycle, "run_action", side_effect=failing):
            self.assertEqual(self.simulate(), 1)
        self.assertIn("FAIL", (self.work / "audit/observation.txt").read_text())
        self.assertEqual(
            json.loads((self.work / "audit/result.json").read_text())["failures"], 1
        )
        with self.assertRaises(ValueError):
            lifecycle.verify_audit(self.work / "audit", self.sha)

    def test_timeout_preserved(self):
        with patch.object(lifecycle.subprocess, "run", side_effect=subprocess.TimeoutExpired("tests", 90)):
            code = lifecycle.run_action(
                Path(sys.executable), self.scratch, self.scratch / "result.json",
                self.scratch / "observation.txt",
            )
        self.assertEqual(code, 124)

    def test_artifact_tamper_missing_extra_symlink_and_wrong_sha(self):
        self.assertEqual(self.simulate(), 0)
        audit = self.work / "audit"
        with self.assertRaises(ValueError):
            lifecycle.verify_audit(audit, "0" * 40)
        for mutation in ("tamper", "missing", "extra", "symlink"):
            with self.subTest(mutation=mutation):
                copied = self.scratch / mutation
                shutil.copytree(audit, copied)
                if mutation == "tamper":
                    (copied / "observation.txt").write_text("changed\n")
                elif mutation == "missing":
                    (copied / "result.json").unlink()
                elif mutation == "extra":
                    (copied / "unexpected.txt").write_text("unexpected\n")
                else:
                    (copied / "result.json").unlink()
                    (copied / "result.json").symlink_to(audit / "result.json")
                with self.assertRaises(ValueError):
                    lifecycle.verify_audit(copied, self.sha)

    def test_no_fixed_test_count_or_skipped_success(self):
        result = dict(tests_run=1, failures=0, errors=0, skipped=0,
                      expected_failures=0, unexpected_successes=0, successful=True)
        self.assertTrue(lifecycle.good_result(result))
        self.assertTrue(lifecycle.good_result(result | {"tests_run": 123}))
        for changes in (
            {"tests_run": 0}, {"skipped": 1}, {"expected_failures": 1},
            {"failures": 1}, {"errors": 1}, {"unexpected_successes": 1},
            {"successful": False}, {"tests_run": True},
        ):
            self.assertFalse(lifecycle.good_result(result | changes))
        self.assertFalse(lifecycle.good_result({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
