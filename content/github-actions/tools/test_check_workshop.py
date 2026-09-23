"""Regression tests for the small workshop checker."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from check_workshop import (
    TRACK, agentic_errors, azure_errors, markdown_errors, reference_errors,
    snippet_errors, solution_kind, workflow_errors,
)


VALID = """
name: Example
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          persist-credentials: false
      - run: echo "$GOAL"
        env:
          GOAL: ${{ inputs.goal }}
"""


class WorkshopChecks(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load(VALID, Loader=yaml.BaseLoader)

    def test_accepts_safe_example_and_preserves_on(self):
        self.assertIn("on", self.workflow)
        self.assertEqual(workflow_errors(self.workflow), [])

    def test_rejects_mutable_action_tag(self):
        self.workflow["jobs"]["test"]["steps"][0]["uses"] = "actions/checkout@v4"
        self.assertTrue(any("full SHA" in error for error in workflow_errors(self.workflow)))

    def test_rejects_persisted_credentials(self):
        del self.workflow["jobs"]["test"]["steps"][0]["with"]
        self.assertTrue(any("persisted credentials" in error for error in workflow_errors(self.workflow)))

    def test_rejects_untrusted_shell_interpolation(self):
        self.workflow["jobs"]["test"]["steps"][1]["run"] = "echo '${{ inputs.goal }}'"
        self.assertTrue(any("untrusted" in error for error in workflow_errors(self.workflow)))

    def test_rejects_missing_timeout(self):
        del self.workflow["jobs"]["test"]["timeout-minutes"]
        self.assertTrue(any("timeout" in error for error in workflow_errors(self.workflow)))

    def test_rejects_privileged_pr_trigger(self):
        self.workflow["on"] = {"pull_request_target": ""}
        self.assertTrue(any("pull_request_target" in error for error in workflow_errors(self.workflow)))

    def test_reusable_calls_do_not_need_runner_timeout(self):
        self.workflow["jobs"]["deploy"] = {
            "uses": "./.github/workflows/reusable-deploy.yml",
            "with": {"deploy-ref": "${{ github.sha }}"},
        }
        self.assertEqual(workflow_errors(self.workflow), [])

    def test_rejects_missing_retention(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["jobs"]["test"]["steps"].append({
            "uses": "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            "with": {"path": "report.txt"},
        })
        self.assertTrue(any("retention" in error for error in workflow_errors(workflow)))

    def test_rejects_old_node_runtime(self):
        self.workflow["jobs"]["test"]["steps"].append({
            "uses": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
            "with": {"node-version": "20"},
        })
        self.assertTrue(any("Node 22" in error for error in workflow_errors(self.workflow)))

    def test_complete_snippet_must_match_solution(self):
        path = Mock()
        path.read_text.return_value = f"# Lesson\n\n```yaml\n{VALID}\n```\n"
        path.relative_to.return_value = "lesson.md"
        self.assertEqual(snippet_errors(path, [self.workflow]), [])
        changed = copy.deepcopy(self.workflow)
        changed["jobs"]["test"]["timeout-minutes"] = "10"
        self.assertTrue(any("matching solution" in error for error in snippet_errors(path, [changed])))

    def test_partial_snippet_is_not_mistaken_for_complete_workflow(self):
        path = Mock()
        path.read_text.return_value = "```yaml\npermissions:\n  contents: read\n```\n"
        self.assertEqual(snippet_errors(path, []), [])

    def test_local_action_input_must_exist_in_companion(self):
        self.workflow["jobs"]["test"]["steps"].append({
            "uses": "./.github/actions/setup-python-env",
            "with": {"database-path": "unused.db"},
        })
        companions = {
            Path("solutions/07-custom-actions/setup-python-env/action.yml"): {
                "inputs": {"python-version": {"default": "3.13"}},
            },
        }
        self.assertTrue(any(
            "database-path" in error for error in reference_errors(self.workflow, companions)
        ))

    def test_local_workflow_requires_declared_inputs(self):
        self.workflow["jobs"]["deploy"] = {
            "uses": "./.github/workflows/reusable-deploy.yml",
        }
        companions = {
            Path("solutions/08-reusable-workflows/reusable-deploy.yml"): {
                "on": {"workflow_call": {"inputs": {"deploy-ref": {"required": "true"}}}},
            },
        }
        self.assertTrue(any("deploy-ref" in error for error in reference_errors(self.workflow, companions)))


class MarkdownChecks(unittest.TestCase):
    def test_links_references_and_heading_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lesson.md").write_text("# Lesson\n\n## Next steps\n")
            index = root / "README.md"
            with patch("check_workshop.ROOT", root):
                index.write_text("[Continue][next]\n\n[next]: lesson.md#next-steps\n")
                self.assertEqual(markdown_errors(index), [])
                index.write_text("[Continue](lesson.md#missing-heading)\n")
                self.assertTrue(any("missing heading" in error for error in markdown_errors(index)))
                index.write_text("[Continue](missing.md)\n")
                self.assertTrue(any("missing link target" in error for error in markdown_errors(index)))
                index.write_text("[Continue][undefined]\n")
                self.assertTrue(any("undefined reference" in error for error in markdown_errors(index)))

    def test_literal_markdown_in_a_code_fence_is_not_a_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "README.md"
            index.write_text("```text\n[Example](does-not-exist.md)\n```\n")
            with patch("check_workshop.ROOT", root):
                self.assertEqual(markdown_errors(index), [])


class WorkflowFormatChecks(unittest.TestCase):
    def setUp(self):
        self.stage = TRACK / "solutions/14-agentic-workflows"
        self.lock = self.stage / "pets-test-plan.lock.yml"
        self.document = yaml.load(self.lock.read_text(), Loader=yaml.BaseLoader)

    def test_only_designated_solutions_get_special_format_handling(self):
        self.assertEqual(solution_kind(self.lock), "agentic")
        self.assertEqual(solution_kind(Path("16-migration/azure-pipelines.yml")), "azure")
        for path in ("other/example.lock.yml", "other/azure-pipelines.yml", "16-migration/migrated-ci.yml"):
            self.assertEqual(solution_kind(Path(path)), "actions")

    def test_compiled_example_keeps_its_own_contract(self):
        self.assertEqual(agentic_errors(self.lock, self.document), [])
        self.assertTrue(workflow_errors(self.document))

    def test_compiled_agent_cannot_gain_write_access(self):
        self.document["jobs"]["agent"]["permissions"]["contents"] = "write"
        self.assertTrue(any("read-only" in item for item in agentic_errors(self.lock, self.document)))

    def test_compiled_safe_outputs_cannot_be_unstaged(self):
        self.document["jobs"]["safe_outputs"]["env"]["GH_AW_SAFE_OUTPUTS_STAGED"] = "false"
        self.assertTrue(any("staged" in item for item in agentic_errors(self.lock, self.document)))

    def test_compiled_approval_cannot_be_removed(self):
        del self.document["jobs"]["activation"]["environment"]
        self.assertTrue(any("approval" in item for item in agentic_errors(self.lock, self.document)))

    def test_compiled_pins_cannot_be_mutable(self):
        step = next(step for step in self.document["jobs"]["agent"]["steps"] if "uses" in step)
        step["uses"] = "github/gh-aw-actions/setup@main"
        self.assertTrue(any("not pinned" in item for item in agentic_errors(self.lock, self.document)))

    def test_source_contract_rejects_new_tools_triggers_and_outputs(self):
        source = (self.stage / "pets-test-plan.md").read_text()
        for original, replacement, diagnostic in (
            ("  bash: false", "  bash: true", "shell"),
            ("  workflow_dispatch:", "  push:", "manual"),
            ("  staged: true", "  staged: false", "staged"),
            ("    max: 1", "    max: 2", "bounded"),
            ("    read-only: true", "    read-only: false", "file-reading"),
            ("max-ai-credits: 100", "max-ai-credits: -1", "max-ai-credits"),
        ):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                lock = root / self.lock.name
                lock.write_text(self.lock.read_text())
                (root / "pets-test-plan.md").write_text(source.replace(original, replacement))
                self.assertTrue(any(diagnostic in item for item in agentic_errors(lock, self.document)))

    def test_missing_agentic_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("missing", agentic_errors(Path(directory) / self.lock.name, self.document)[0])

    def test_azure_format_still_enforces_manual_bounded_ci(self):
        source = {"trigger": "none", "pr": "none", "jobs": [{"job": "api", "timeoutInMinutes": "10"}]}
        self.assertEqual(azure_errors(source), [])
        source["trigger"] = ["main"]
        source["jobs"][0]["timeoutInMinutes"] = "0"
        findings = azure_errors(source)
        self.assertTrue(any("trigger" in item for item in findings))
        self.assertTrue(any("timeout" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
