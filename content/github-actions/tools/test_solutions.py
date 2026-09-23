"""Exercise the actual solution shell commands without calling GitHub or Azure."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from check_workshop import TRACK, agentic_source, solution_kind


def solution(relative):
    return yaml.load((TRACK / "solutions" / relative).read_text(), Loader=yaml.BaseLoader)


def run_step(script, cwd, **variables):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        cwd=cwd,
        env={**os.environ, **variables},
        capture_output=True,
        text=True,
        timeout=30,
    )


def condition_result(expression, context):
    """Evaluate only the boolean-expression subset used by these solutions."""
    expression = expression.removeprefix("${{").removesuffix("}}").strip()
    token_pattern = re.compile(r"\s*(\|\||&&|==|!=|!|\(|\)|,|'(?:[^']|'')*'|[A-Za-z_][\w.-]*)")
    tokens = []
    offset = 0
    while offset < len(expression):
        if not expression[offset:].strip():
            break
        match = token_pattern.match(expression, offset)
        if not match:
            raise AssertionError(f"Unsupported condition syntax: {expression[offset:]}")
        tokens.append(match[1])
        offset = match.end()
    index = 0

    def take(token):
        nonlocal index
        if index < len(tokens) and tokens[index] == token:
            index += 1
            return True
        return False

    def atom():
        nonlocal index
        if take("!"):
            return not atom()
        if take("("):
            value = disjunction()
            if not take(")"):
                raise AssertionError("Missing closing parenthesis")
            return value
        if index >= len(tokens):
            raise AssertionError("Missing condition operand")
        token = tokens[index]
        index += 1
        if token == "format" and take("("):
            template = atom()
            if not take(","):
                raise AssertionError("Expected a format argument")
            argument = atom()
            if not take(")"):
                raise AssertionError("Expected the end of format")
            return template.replace("{0}", str(argument))
        if token.startswith("'"):
            return token[1:-1].replace("''", "'")
        if token in ("true", "false"):
            return token == "true"
        value = context
        for key in token.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        return value

    def comparison():
        value = atom()
        if index < len(tokens) and tokens[index] in ("==", "!="):
            operator = tokens[index]
            take(operator)
            other = atom()
            if isinstance(value, str) and isinstance(other, str):
                value, other = value.casefold(), other.casefold()
            return value == other if operator == "==" else value != other
        return value

    def conjunction():
        value = comparison()
        while take("&&"):
            other = comparison()
            value = bool(value) and bool(other)
        return value

    def disjunction():
        value = conjunction()
        while take("||"):
            other = conjunction()
            value = bool(value) or bool(other)
        return value

    result = disjunction()
    if index != len(tokens):
        raise AssertionError(f"Unexpected condition tokens: {tokens[index:]}")
    return bool(result)


class DeploymentConditionTests(unittest.TestCase):
    def context(self, event_name="workflow_run", ref="refs/heads/main", **upstream):
        context = {
            "github": {
                "event_name": event_name,
                "ref": ref,
                "repository": "example/pets",
                "event": {
                    "repository": {"default_branch": "main"},
                    "workflow_run": {
                        "event": "push",
                        "head_branch": "main",
                        "head_repository": {"full_name": "example/pets"},
                        "conclusion": "success",
                        **upstream,
                    },
                },
            },
            "inputs": {"deploy": False},
        }
        if event_name != "workflow_run":
            del context["github"]["event"]["workflow_run"]
        return context

    def test_core_automatic_deployment_trust_boundary(self):
        for path in ("06-deploy-azure/azure-dev.yml", "08-reusable-workflows/azure-dev.yml"):
            workflow = solution(path)
            condition = workflow["jobs"]["deploy"]["if"]
            cases = [
                (self.context(), True),
                (self.context(conclusion="failure"), False),
                (self.context(conclusion="cancelled"), False),
                (self.context(conclusion="skipped"), False),
                (self.context(event="pull_request"), False),
                (self.context(head_branch="feature"), False),
                (self.context(head_repository={"full_name": "outsider/pets"}), False),
                (self.context(event_name="pull_request"), False),
                (self.context(event_name="workflow_dispatch"), False),
                (self.context(event_name="workflow_dispatch", ref="refs/heads/feature"), False),
            ]
            for context, expected in cases:
                with self.subTest(path=path, context=context):
                    triggered = context["github"]["event_name"] in workflow["on"]
                    self.assertEqual(triggered and condition_result(condition, context), expected)

    def test_manual_rollback_workflow_is_main_only(self):
        workflow = solution("08-reusable-workflows/manual-deploy.yml")
        for event in ("pull_request", "push", "workflow_dispatch"):
            for ref in ("refs/heads/main", "refs/heads/feature"):
                context = self.context(event_name=event, ref=ref)
                triggered = event in workflow["on"]
                with self.subTest(event=event, ref=ref):
                    self.assertEqual(
                        triggered and condition_result(workflow["jobs"]["deploy"]["if"], context),
                        event == "workflow_dispatch" and ref == "refs/heads/main",
                    )

    def test_capstone_deployment_is_explicit_and_main_only(self):
        condition = solution("15-capstone/capstone.yml")["jobs"]["deploy"]["if"]
        for event in ("pull_request", "push", "workflow_dispatch"):
            for ref in ("refs/heads/main", "refs/heads/feature"):
                for deploy in (False, True):
                    context = self.context(event_name=event, ref=ref)
                    context["inputs"]["deploy"] = deploy
                    expected = event == "workflow_dispatch" and ref == "refs/heads/main" and deploy
                    with self.subTest(event=event, ref=ref, deploy=deploy):
                        self.assertEqual(condition_result(condition, context), expected)

    def test_reusable_deployment_rechecks_the_callers_trust_and_sha(self):
        condition = solution("08-reusable-workflows/reusable-deploy.yml")["jobs"]["deploy"]["if"]
        sha = "a" * 40
        context = self.context(head_sha=sha)
        context["inputs"]["deploy-ref"] = sha
        self.assertTrue(condition_result(condition, context))
        context["inputs"]["deploy-ref"] = "b" * 40
        self.assertFalse(condition_result(condition, context))
        for event, branch, repository in (
            ("pull_request", "main", "example/pets"),
            ("push", "feature", "example/pets"),
            ("push", "main", "outsider/pets"),
        ):
            context = self.context(
                head_sha=sha, event=event, head_branch=branch,
                head_repository={"full_name": repository},
            )
            context["inputs"]["deploy-ref"] = sha
            self.assertFalse(condition_result(condition, context))
        for ref in ("refs/heads/main", "refs/heads/feature"):
            context = self.context(event_name="workflow_dispatch", ref=ref)
            context["inputs"]["deploy-ref"] = sha
            self.assertEqual(condition_result(condition, context), ref == "refs/heads/main")

    def test_selected_deployment_commit_is_not_default_branch_head(self):
        core = solution("06-deploy-azure/azure-dev.yml")["jobs"]["deploy"]
        checkout = next(step for step in core["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(
            checkout["with"]["ref"],
            "${{ github.event.workflow_run.head_sha }}",
        )
        caller = solution("08-reusable-workflows/azure-dev.yml")["jobs"]["deploy"]
        self.assertEqual(
            caller["with"]["deploy-ref"],
            "${{ github.event.workflow_run.head_sha }}",
        )
        capstone = solution("15-capstone/capstone.yml")["jobs"]["deploy"]
        self.assertEqual(capstone["with"]["deploy-ref"], "${{ github.sha }}")
        self.assertEqual(capstone["with"]["environment-name"], "pets-production")


class GateTests(unittest.TestCase):
    def test_each_non_success_result_blocks_every_aggregate_gate(self):
        found = 0
        for path in sorted((TRACK / "solutions").rglob("*.yml")):
            if solution_kind(path) != "actions":
                continue
            data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            for name, job in data.get("jobs", {}).items():
                if name not in {"tests-passed", "capstone-passed"}:
                    continue
                found += 1
                with self.subTest(path=path, gate=name):
                    self.assertIn(job["if"], ("always()", "${{ always() }}"))
                    step = job["steps"][0]
                    variables = step["env"]
                    referenced_jobs = {
                        expression.removeprefix("${{ needs.").removesuffix(".result }}")
                        for expression in variables.values()
                    }
                    self.assertEqual(referenced_jobs, set(job["needs"]))
                    passing = {key: "success" for key in variables}
                    passing["GITHUB_STEP_SUMMARY"] = os.devnull
                    result = run_step(step["run"], TRACK, **passing)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for key in variables:
                        for status in ("failure", "cancelled", "skipped"):
                            result = run_step(step["run"], TRACK, **{**passing, key: status})
                            self.assertNotEqual(result.returncode, 0, (path, key, status))
        self.assertGreaterEqual(found, 2, "core and capstone gates must both be covered")


class InputValidationTests(unittest.TestCase):
    def test_python_action_rejects_unrecognized_or_shell_like_versions(self):
        action = solution("07-custom-actions/setup-python-env/action.yml")
        script = action["runs"]["steps"][0]["run"]
        for version in ("3.12", "3.13", "3.14"):
            self.assertEqual(run_step(script, TRACK, PYTHON_VERSION=version).returncode, 0)
        for version in ("3.9", "latest", "", "$(echo injected)", "3.13; echo injected"):
            with self.subTest(version=version):
                self.assertNotEqual(run_step(script, TRACK, PYTHON_VERSION=version).returncode, 0)

    def test_deployment_requires_a_full_sha(self):
        for path in ("06-deploy-azure/azure-dev.yml", "08-reusable-workflows/reusable-deploy.yml"):
            steps = solution(path)["jobs"]["deploy"]["steps"]
            script = next(step["run"] for step in steps if step.get("name") == "Validate deployment SHA")
            self.assertEqual(run_step(script, TRACK, DEPLOY_SHA="a" * 40).returncode, 0)
            for value in ("main", "v1.0", "abcdef", "", "$(echo injected)", "a" * 41):
                with self.subTest(path=path, value=value):
                    self.assertNotEqual(run_step(script, TRACK, DEPLOY_SHA=value).returncode, 0)


class AIWorkflowTests(unittest.TestCase):
    def test_cli_defaults_to_dry_run_and_needs_main_for_both_paths(self):
        workflow = solution("13-copilot-cli/copilot-cli.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        dry_input = workflow["on"]["workflow_dispatch"]["inputs"]["dry_run"]
        self.assertEqual(dry_input["default"], "true")
        self.assertEqual(dry_input["type"], "boolean")
        self.assertEqual(workflow["jobs"]["approved-cli"]["environment"], "pets-copilot")
        self.assertNotIn("${{ secrets.", yaml.dump(workflow["jobs"]["dry-run"]))
        for ref in ("refs/heads/main", "refs/heads/feature", "refs/tags/main"):
            for dry_run in (False, True):
                context = {
                    "github": {"ref": ref, "event": {"repository": {"default_branch": "main"}}},
                    "inputs": {"dry_run": dry_run},
                }
                with self.subTest(ref=ref, dry_run=dry_run):
                    self.assertEqual(
                        condition_result(workflow["jobs"]["dry-run"]["if"], context),
                        ref == "refs/heads/main" and dry_run,
                    )
                    self.assertEqual(
                        condition_result(workflow["jobs"]["approved-cli"]["if"], context),
                        ref == "refs/heads/main" and not dry_run,
                    )

    def test_agentic_default_branch_gate_precedes_inference(self):
        source = agentic_source(TRACK / "solutions/14-agentic-workflows/pets-test-plan.md")
        workflow = solution("14-agentic-workflows/pets-test-plan.lock.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["jobs"]["activation"]["environment"], "pets-agentic")
        self.assertEqual(workflow["jobs"]["agent"]["needs"], "activation")
        for ref in ("refs/heads/main", "refs/heads/feature", "refs/tags/main"):
            context = {"github": {"ref": ref, "event": {"repository": {"default_branch": "main"}}}}
            with self.subTest(ref=ref):
                self.assertEqual(condition_result(source["if"], context), ref == "refs/heads/main")
                self.assertEqual(
                    condition_result(workflow["jobs"]["pre_activation"]["if"], context),
                    ref == "refs/heads/main",
                )
        steps = workflow["jobs"]["agent"]["steps"]
        execution = next(step for step in steps if step.get("id") == "agentic_execution")
        self.assertEqual(execution["timeout-minutes"], "5")
        self.assertIn("secrets.COPILOT_GITHUB_TOKEN", yaml.dump(steps))
        self.assertIn("awf --config", execution["run"])
        self.assertIn("github(get_file_contents)", execution["run"])
        self.assertNotIn("actions/checkout@", yaml.dump(steps))
        safe_steps = yaml.dump(workflow["jobs"]["safe_outputs"]["steps"])
        self.assertIn("GH_AW_SAFE_OUTPUTS_STAGED", safe_steps)
        self.assertIn("needs.detection.result == 'success'", workflow["jobs"]["safe_outputs"]["if"])


@unittest.skipUnless(shutil.which("sha256sum"), "artifact shell commands require sha256sum")
class ArtifactTests(unittest.TestCase):
    def test_downstream_reruns_use_the_producers_artifact_id(self):
        for relative in (
            "10-artifacts/artifacts.yml",
            "12-environments/protected-release.yml",
            "15-capstone/capstone.yml",
        ):
            data = solution(relative)
            for name, job in data["jobs"].items():
                for step in job.get("steps", []):
                    if not step.get("uses", "").startswith("actions/download-artifact@"):
                        continue
                    with self.subTest(solution=relative, consumer=name):
                        options = step["with"]
                        self.assertNotIn("name", options)
                        self.assertEqual(options["merge-multiple"], "true")
                        match = re.fullmatch(
                            r"\$\{\{ needs\.([\w-]+)\.outputs\.artifact-id \}\}",
                            options["artifact-ids"],
                        )
                        self.assertIsNotNone(match)
                        producer = match[1]
                        needs = job["needs"] if isinstance(job["needs"], list) else [job["needs"]]
                        self.assertIn(producer, needs)
                        output = data["jobs"][producer]["outputs"]["artifact-id"]
                        self.assertEqual(output, "${{ steps.upload.outputs.artifact-id }}")
                        upload = next(
                            item for item in data["jobs"][producer]["steps"] if item.get("id") == "upload"
                        )
                        self.assertTrue(upload["uses"].startswith("actions/upload-artifact@"))
                        guard = next(
                            item for item in job["steps"]
                            if options["artifact-ids"] in item.get("env", {}).values()
                        )
                        variable = next(
                            key for key, value in guard["env"].items() if value == options["artifact-ids"]
                        )
                        self.assertEqual(run_step(guard["run"], TRACK, **{variable: "101"}).returncode, 0)
                        for invalid in ("", "missing", "101,102", "$(echo injected)"):
                            self.assertNotEqual(
                                run_step(guard["run"], TRACK, **{variable: invalid}).returncode, 0
                            )
                        # An unchanged successful producer retains its original output.
                        for consumer_attempt in (1, 2):
                            context = {
                                "github": {"run_attempt": consumer_attempt},
                                "needs": {producer: {"outputs": {"artifact-id": "101"}}},
                            }
                            selected = context
                            for key in options["artifact-ids"].removeprefix("${{ ").removesuffix(" }}").split("."):
                                selected = selected[key]
                            self.assertEqual(selected, "101")

    def test_build_handoff_and_integrity_failures(self):
        for relative, build_job in (
            ("10-artifacts/artifacts.yml", "build-client"),
            ("12-environments/protected-release.yml", "build"),
            ("15-capstone/capstone.yml", "build-client"),
        ):
            with self.subTest(solution=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                dist = root / "app/client/dist"
                dist.mkdir(parents=True)
                (dist / "index.html").write_text("<h1>Shelter fixture</h1>")
                runner_temp = root / "runner"
                runner_temp.mkdir()
                data = solution(relative)
                package = next(
                    step["run"] for step in data["jobs"][build_job]["steps"]
                    if "tar -czf" in step.get("run", "")
                )
                verify = next(
                    step["run"] for step in data["jobs"]["verify"]["steps"]
                    if "sha256sum --check" in step.get("run", "")
                )
                sha = "a" * 40
                result = run_step(package, root, RUNNER_TEMP=str(runner_temp), GITHUB_SHA=sha)
                self.assertEqual(result.returncode, 0, result.stderr)
                produced = runner_temp / "pets-build"
                self.assertEqual(
                    {file.name for file in produced.iterdir()},
                    {"site.tar.gz", "commit.txt", "SHA256SUMS"},
                )
                consumer = root / "consumer"
                shutil.copytree(produced, consumer)
                variables = {"EXPECTED_SHA": sha, "GITHUB_STEP_SUMMARY": str(root / "summary")}
                result = run_step(verify, consumer, **variables)
                self.assertEqual(result.returncode, 0, result.stderr)
                with (consumer / "site.tar.gz").open("ab") as archive:
                    archive.write(b"tampering")
                self.assertNotEqual(run_step(verify, consumer, **variables).returncode, 0)
                shutil.copyfile(produced / "site.tar.gz", consumer / "site.tar.gz")
                self.assertNotEqual(
                    run_step(verify, consumer, **{**variables, "EXPECTED_SHA": "b" * 40}).returncode,
                    0,
                )
                (consumer / "site.tar.gz").unlink()
                self.assertNotEqual(run_step(verify, consumer, **variables).returncode, 0)

    def test_diagnostics_do_not_hide_browser_failure(self):
        for relative in ("10-artifacts/artifacts.yml", "15-capstone/capstone.yml"):
            with self.subTest(solution=relative):
                job = solution(relative)["jobs"]["test-e2e"]
                self.assertNotIn("continue-on-error", job)
                test = next(step for step in job["steps"] if step.get("run") == "npm run test:e2e")
                self.assertNotIn("continue-on-error", test)
                upload = job["steps"][-1]
                self.assertEqual(upload["if"], "${{ !cancelled() }}")
                self.assertEqual(upload["with"]["if-no-files-found"], "warn")
                self.assertEqual(
                    upload["with"]["path"].split(),
                    ["app/client/playwright-report/", "app/client/test-results/"],
                )


if __name__ == "__main__":
    unittest.main()
