"""Offline checks; the CLI boundary is mocked and no model is called."""

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
spec = importlib.util.spec_from_file_location("pets_report", STAGE / "report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.scratch = STAGE / ".validation" / uuid.uuid4().hex
        self.checkout = self.scratch / "checkout"
        self.work = self.scratch / "work"
        (self.checkout / "app/server").mkdir(parents=True)
        shutil.copyfile(ROOT / "app/server/app.py", self.checkout / "app/server/app.py")
        self.cli = self.scratch / "fake-cli"
        self.cli.write_text("This file is never executed.\n")
        self.auth = patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "github_pat_fake_for_test"})
        self.auth.start()

    def tearDown(self):
        self.auth.stop()
        shutil.rmtree(self.scratch)
        if not any((STAGE / ".validation").iterdir()):
            (STAGE / ".validation").rmdir()

    def test_dry_run_never_invokes_cli_or_checks_auth(self):
        with patch.object(report, "invoke") as invoke:
            with patch.object(report.os, "environ", {}):
                report.make_report(self.checkout, self.work, "dry")
            invoke.assert_not_called()
        metadata = json.loads((self.work / "report/metadata.json").read_text())
        self.assertFalse(metadata["model_called"])
        self.assertIsNone(metadata["cli_version"])
        self.assertEqual({p.name for p in (self.work / "context").iterdir()}, {"app.py"})

    def test_live_invocation_has_minimal_environment_and_read_only_tools(self):
        help_text = " ".join(flag.split("=")[0] for flag in report.FLAGS)
        calls = []

        def invoke(command, context, environment, output, seconds, **kwargs):
            calls.append((command, environment.copy()))
            if "--version" in command:
                return report.VERSION
            if "--help" in command:
                return help_text
            return "This Flask API returns dogs. github_pat_fake_for_test"

        with patch.object(report, "invoke", side_effect=invoke):
            report.make_report(self.checkout, self.work, "live", self.cli)
        for _, environment in calls[:2]:
            self.assertNotIn("COPILOT_GITHUB_TOKEN", environment)
        command, environment = calls[-1]
        self.assertEqual(environment["COPILOT_GITHUB_TOKEN"], "github_pat_fake_for_test")
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertIn("--available-tools=view", command)
        self.assertIn("--deny-tool=shell", command)
        self.assertIn("--deny-tool=write", command)
        self.assertIn("--no-custom-instructions", command)
        self.assertIn("--disable-builtin-mcps", command)
        self.assertNotIn("github_pat_fake_for_test", (self.work / "report/report.txt").read_text())

    def test_missing_restrictions_or_wrong_version_fail_before_model(self):
        for replies in ([report.VERSION, "help without restrictions"], ["0.0.1"]):
            with self.subTest(replies=replies):
                with patch.object(report, "invoke", side_effect=replies) as invoke:
                    with self.assertRaises(ValueError):
                        report.make_report(self.checkout, self.work, "live", self.cli)
                    self.assertLessEqual(invoke.call_count, 2)
                self.assertFalse((self.work / "report").exists())
                shutil.rmtree(self.work)

    def test_missing_token_does_not_fall_back(self):
        with patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "", "GH_TOKEN": "not-used"}):
            with patch.object(report, "invoke") as invoke:
                with self.assertRaises(ValueError):
                    report.make_report(self.checkout, self.work, "live", self.cli)
                invoke.assert_not_called()

    def test_context_mutation_rejected(self):
        help_text = " ".join(flag.split("=")[0] for flag in report.FLAGS)

        def invoke(command, context, *args, **kwargs):
            if "--version" in command:
                return report.VERSION
            if "--help" in command:
                return help_text
            (context / "unexpected.txt").write_text("changed\n")
            return "A report"

        with patch.object(report, "invoke", side_effect=invoke):
            with self.assertRaises(ValueError):
                report.make_report(self.checkout, self.work, "live", self.cli)
        self.assertFalse((self.work / "report").exists())

    def test_empty_oversized_and_failed_process_output_rejected(self):
        for program in ("pass", "print('x' * 20000)", "raise SystemExit(1)"):
            with self.subTest(program=program):
                with self.assertRaises(ValueError):
                    report.invoke(
                        [sys.executable, "-c", program], self.scratch, {},
                        self.scratch / "output.txt", 5,
                    )

    def test_process_timeout_rejected(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            report.invoke(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                self.scratch, {}, self.scratch / "output.txt", 0.05,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
