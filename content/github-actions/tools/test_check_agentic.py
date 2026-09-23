"""Test freshness-check failure modes without running a compiler or AI."""

import subprocess
import unittest
from unittest.mock import patch

import check_agentic


class AgenticFreshnessChecks(unittest.TestCase):
    def command(self, args, **kwargs):
        if args[-1] == "version":
            return subprocess.CompletedProcess(args, 0, "gh aw version v0.88.8\n")
        return subprocess.CompletedProcess(args, 0, "")

    def test_compile_is_isolated_and_does_not_dispatch(self):
        with patch("check_agentic.subprocess.run", side_effect=self.command) as run:
            check_agentic.check(["gh", "aw"])
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[-1], ["gh", "aw", "compile", "pets-test-plan", "--strict", "--no-check-update"])
        self.assertNotEqual(run.call_args_list[-1].kwargs["cwd"], check_agentic.TRACK)
        self.assertFalse(any("run" in call or "trial" in call for call in calls))

    def test_wrong_compiler_stops_before_compilation(self):
        result = subprocess.CompletedProcess([], 0, "gh aw version v0.79.8\n")
        with patch("check_agentic.subprocess.run", return_value=result) as run:
            with self.assertRaisesRegex(ValueError, "expected gh-aw"):
                check_agentic.check(["gh", "aw"])
        self.assertEqual(run.call_count, 1)

    def test_failed_compilation_is_not_a_successful_freshness_check(self):
        def fail(args, **kwargs):
            if "compile" in args:
                raise subprocess.CalledProcessError(1, args)
            return self.command(args, **kwargs)

        with patch("check_agentic.subprocess.run", side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                check_agentic.check(["gh", "aw"])

    def test_lock_and_pin_drift_are_both_rejected(self):
        for relative, diagnostic in (
            (".github/workflows/pets-test-plan.lock.yml", "stale agentic lockfile"),
            (".github/aw/actions-lock.json", "stale action pins"),
        ):
            def change(args, **kwargs):
                if "compile" in args:
                    target = kwargs["cwd"] / relative
                    target.write_text(target.read_text() + "\n")
                return self.command(args, **kwargs)

            with self.subTest(relative=relative), patch("check_agentic.subprocess.run", side_effect=change):
                with self.assertRaisesRegex(ValueError, diagnostic):
                    check_agentic.check(["gh", "aw"])


if __name__ == "__main__":
    unittest.main()
