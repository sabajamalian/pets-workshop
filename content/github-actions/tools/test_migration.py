"""Check migration parity and real shell steps without contacting either CI service."""

import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from check_workshop import TRACK
from test_solutions import run_step, solution


JOB_MAP = {
    "TestApi": "test-api",
    "TestE2E": "test-e2e",
    "BuildClient": "build-client",
    "Verify": "verify",
    "MigrationPassed": "migration-passed",
}


def migration():
    source = solution("16-migration/azure-pipelines.yml")
    target = solution("16-migration/migrated-ci.yml")
    jobs = {job["job"]: job for job in source["stages"][0]["jobs"]}
    return source, jobs, target


def dependencies(job, key):
    value = job.get(key, [])
    return [value] if isinstance(value, str) else value


def command_step(job, command, key):
    return next(
        step for step in job["steps"]
        if command in [line.strip() for line in step.get(key, "").splitlines()]
    )


class MigrationParityTests(unittest.TestCase):
    def setUp(self):
        self.source, self.jobs, self.target = migration()

    def test_examples_are_manual_and_do_not_deploy(self):
        self.assertEqual(self.source["trigger"], "none")
        self.assertEqual(self.source["pr"], "none")
        self.assertNotIn("resources", self.source)
        self.assertNotIn("schedules", self.source)
        self.assertEqual(set(self.target["on"]), {"workflow_dispatch"})
        self.assertEqual(self.target["permissions"], {"contents": "read"})
        self.assertNotIn("stages", self.target)
        for job in self.target["jobs"].values():
            self.assertNotIn("environment", job)
            self.assertNotIn("permissions", job)
            self.assertNotIn("uses", job)
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertEqual(step["with"]["persist-credentials"], "false")
        for job in self.jobs.values():
            self.assertNotIn("deployment", job)
            self.assertNotIn("environment", job)
            for step in job["steps"]:
                if step.get("checkout") == "self":
                    self.assertEqual(step["persistCredentials"], "false")

    def test_stage_job_graph_and_timeouts_match(self):
        self.assertNotIn("jobs", self.source)
        self.assertEqual([stage["stage"] for stage in self.source["stages"]], ["Validate"])
        self.assertEqual(set(self.jobs), set(JOB_MAP))
        self.assertEqual(set(self.target["jobs"]), set(JOB_MAP.values()))
        expected = {
            "TestApi": [],
            "TestE2E": [],
            "BuildClient": [],
            "Verify": ["BuildClient"],
            "MigrationPassed": ["TestApi", "TestE2E", "BuildClient", "Verify"],
        }
        for source_name, target_name in JOB_MAP.items():
            with self.subTest(job=source_name):
                source_job = self.jobs[source_name]
                target_job = self.target["jobs"][target_name]
                self.assertEqual(dependencies(source_job, "dependsOn"), expected[source_name])
                self.assertEqual(
                    dependencies(target_job, "needs"),
                    [JOB_MAP[name] for name in expected[source_name]],
                )
                self.assertEqual(
                    int(source_job["timeoutInMinutes"]), int(target_job["timeout-minutes"])
                )
                self.assertTrue(0 < int(source_job["timeoutInMinutes"]) <= 15)

    def test_shared_toolchains_and_real_pets_commands_match(self):
        for variable, expected in (("CI", "true"), ("PYTHONDONTWRITEBYTECODE", "1")):
            self.assertEqual(self.source["variables"][variable], expected)
            self.assertEqual(self.target["env"][variable], expected)
        for source_name in ("TestApi", "TestE2E"):
            source_job = self.jobs[source_name]
            target_job = self.target["jobs"][JOB_MAP[source_name]]
            setup_source = next(
                step for step in source_job["steps"] if step.get("task") == "UsePythonVersion@0"
            )
            setup_target = next(
                step for step in target_job["steps"]
                if step.get("uses", "").startswith("actions/setup-python@")
            )
            self.assertEqual(setup_source["inputs"]["versionSpec"], "3.13")
            self.assertEqual(setup_target["with"]["python-version"], "3.13")
            install = "python -m pip install -r app/server/requirements.txt"
            command_step(source_job, install, "bash")
            command_step(target_job, install, "run")
        for source_name in ("TestE2E", "BuildClient"):
            source_job = self.jobs[source_name]
            target_job = self.target["jobs"][JOB_MAP[source_name]]
            setup_source = next(
                step for step in source_job["steps"] if step.get("task") == "UseNode@1"
            )
            setup_target = next(
                step for step in target_job["steps"]
                if step.get("uses", "").startswith("actions/setup-node@")
            )
            self.assertEqual(setup_source["inputs"]["version"], "22.x")
            self.assertEqual(setup_target["with"]["node-version"], "22")
            commands = ["npm ci"]
            if source_name == "TestE2E":
                commands += [
                    "npx playwright install --with-deps chromium",
                    "npm run test:e2e -- --project=chromium",
                ]
            else:
                commands.append("npm run build")
            for command in commands:
                source_step = command_step(source_job, command, "bash")
                target_step = command_step(target_job, command, "run")
                self.assertEqual(
                    source_step["workingDirectory"], "$(Build.SourcesDirectory)/app/client"
                )
                self.assertEqual(target_step["working-directory"], "app/client")
        for job, key, directory_key in (
            (self.jobs["TestApi"], "bash", "workingDirectory"),
            (self.target["jobs"]["test-api"], "run", "working-directory"),
        ):
            test = command_step(job, "python -m unittest test_app -v", key)
            self.assertTrue(test[directory_key].endswith("app/server"))
            self.assertEqual(test["env"]["DATABASE_PATH"], ":memory:")
            self.assertEqual(test["env"]["PYTHONDONTWRITEBYTECODE"], "1")

    def test_azure_uses_native_artifacts_and_the_producers_name(self):
        build = self.jobs["BuildClient"]
        package = next(step for step in build["steps"] if step.get("name") == "package")
        self.assertIn("variable=artifactName;isOutput=true", package["bash"])
        self.assertEqual(
            package["env"]["BUILD_ARTIFACT_NAME"],
            "pets-migration-build-$(Build.BuildId)-$(System.StageAttempt)-$(System.JobAttempt)",
        )
        upload = next(
            step for step in build["steps"] if step.get("task") == "PublishPipelineArtifact@1"
        )
        self.assertEqual(upload["inputs"]["artifact"], "$(package.artifactName)")
        self.assertEqual(upload["inputs"]["publishLocation"], "pipeline")
        verify = self.jobs["Verify"]
        self.assertEqual(
            verify["variables"]["buildArtifactName"],
            "$[ dependencies.BuildClient.outputs['package.artifactName'] ]",
        )
        download = next(
            step for step in verify["steps"] if step.get("task") == "DownloadPipelineArtifact@2"
        )
        self.assertEqual(download["inputs"]["buildType"], "current")
        self.assertEqual(download["inputs"]["artifactName"], "$(buildArtifactName)")
        self.assertEqual(download["inputs"]["targetPath"], "$(Pipeline.Workspace)/verified-build")

    def test_github_consumer_uses_original_producer_id_on_reruns(self):
        build = self.target["jobs"]["build-client"]
        self.assertEqual(build["outputs"]["artifact-id"], "${{ steps.upload.outputs.artifact-id }}")
        upload = next(step for step in build["steps"] if step.get("id") == "upload")
        self.assertTrue(upload["uses"].startswith("actions/upload-artifact@"))
        self.assertEqual(upload["with"]["if-no-files-found"], "error")
        download = next(
            step for step in self.target["jobs"]["verify"]["steps"]
            if step.get("uses", "").startswith("actions/download-artifact@")
        )
        self.assertEqual(
            download["with"]["artifact-ids"], "${{ needs.build-client.outputs.artifact-id }}"
        )
        self.assertEqual(download["with"]["merge-multiple"], "true")
        self.assertNotIn("name", download["with"])
        for attempt in (1, 2, 3):
            context = {
                "github": {"run_attempt": attempt},
                "needs": {"build-client": {"outputs": {"artifact-id": "101"}}},
            }
            selected = context
            expression = download["with"]["artifact-ids"].removeprefix("${{ ").removesuffix(" }}")
            for key in expression.split("."):
                selected = selected[key]
            self.assertEqual(selected, "101")

    def test_diagnostics_remain_available_without_masking_failure(self):
        source = self.jobs["TestE2E"]
        target = self.target["jobs"]["test-e2e"]
        for jobs, bypass in ((self.jobs, "continueOnError"), (self.target["jobs"], "continue-on-error")):
            for job in jobs.values():
                self.assertNotIn(bypass, job)
                for step in job["steps"]:
                    self.assertNotIn(bypass, step)
        self.assertEqual(source["steps"][-2]["condition"], "not(canceled())")
        self.assertEqual(source["steps"][-1]["task"], "PublishPipelineArtifact@1")
        self.assertEqual(
            source["steps"][-1]["condition"],
            "and(not(canceled()), eq(variables['hasBrowserReport'], 'true'))",
        )
        self.assertEqual(target["steps"][-1]["if"], "${{ !cancelled() }}")
        self.assertEqual(target["steps"][-1]["with"]["if-no-files-found"], "warn")
        self.assertEqual(target["steps"][-1]["with"]["retention-days"], "7")
        self.assertEqual(
            target["steps"][-1]["with"]["path"].split(),
            ["app/client/playwright-report/", "app/client/test-results/"],
        )

    def test_gate_inputs_reference_every_required_job(self):
        source_gate = self.jobs["MigrationPassed"]
        target_gate = self.target["jobs"]["migration-passed"]
        source_step = next(step for step in source_gate["steps"] if "bash" in step)
        target_step = target_gate["steps"][0]
        for variable, output, producer in (
            ("API_RESULT", "apiResult", "TestApi"),
            ("E2E_RESULT", "e2eResult", "TestE2E"),
            ("BUILD_RESULT", "buildResult", "BuildClient"),
            ("VERIFY_RESULT", "verifyResult", "Verify"),
        ):
            with self.subTest(producer=producer):
                self.assertEqual(
                    source_gate["variables"][output], f"$[ dependencies.{producer}.result ]"
                )
                self.assertEqual(source_step["env"][variable], f"$({output})")
                self.assertEqual(
                    target_step["env"][variable],
                    "${{ needs." + JOB_MAP[producer] + ".result }}",
                )


@unittest.skipUnless(shutil.which("bash"), "migration shell commands require Bash")
class MigrationGateTests(unittest.TestCase):
    def test_each_non_success_dependency_blocks_both_gates(self):
        _, source, target = migration()
        for job, key, success, failures in (
            (source["MigrationPassed"], "bash", "Succeeded", ("Failed", "Skipped", "Canceled", "SucceededWithIssues", "")),
            (target["jobs"]["migration-passed"], "run", "success", ("failure", "skipped", "cancelled", "neutral", "")),
        ):
            condition = "condition" if key == "bash" else "if"
            self.assertEqual(job[condition], "always()")
            step = next(step for step in job["steps"] if key in step)
            self.assertEqual(
                set(step["env"]), {"API_RESULT", "E2E_RESULT", "BUILD_RESULT", "VERIFY_RESULT"}
            )
            passing = {variable: success for variable in step["env"]}
            result = run_step(step[key], TRACK, **passing)
            self.assertEqual(result.returncode, 0, result.stderr)
            for variable in passing:
                for status in failures:
                    with self.subTest(platform=key, variable=variable, status=status):
                        result = run_step(step[key], TRACK, **{**passing, variable: status})
                        self.assertNotEqual(result.returncode, 0)

    def test_missing_artifact_selection_is_rejected_before_download(self):
        _, source, target = migration()
        guard = target["jobs"]["verify"]["steps"][0]
        self.assertEqual(
            guard["env"]["ARTIFACT_ID"], "${{ needs.build-client.outputs.artifact-id }}"
        )
        self.assertEqual(run_step(guard["run"], TRACK, ARTIFACT_ID="101").returncode, 0)
        for value in ("", "missing", "101,102"):
            with self.subTest(artifact_id=value):
                self.assertNotEqual(run_step(guard["run"], TRACK, ARTIFACT_ID=value).returncode, 0)
        guard = source["Verify"]["steps"][1]
        self.assertEqual(guard["env"]["BUILD_ARTIFACT_NAME"], "$(buildArtifactName)")
        self.assertEqual(
            run_step(guard["bash"], TRACK, BUILD_ARTIFACT_NAME="pets-build-101").returncode, 0
        )
        self.assertNotEqual(run_step(guard["bash"], TRACK, BUILD_ARTIFACT_NAME="").returncode, 0)


@unittest.skipUnless(shutil.which("bash"), "migration shell commands require Bash")
class MigrationHandoffTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(f".migration-contract-{uuid4().hex}")
        self.workspace.mkdir()
        self.addCleanup(shutil.rmtree, self.workspace)
        self.workspace = self.workspace.resolve()

    @unittest.skipUnless(shutil.which("sha256sum"), "artifact shell commands require sha256sum")
    def test_real_packaging_and_verification_reject_corrupt_or_wrong_builds(self):
        _, source, target = migration()
        sha = "a" * 40
        for provider in ("azure", "github"):
            with self.subTest(provider=provider):
                root = self.workspace / provider
                dist = root / "app/client/dist"
                dist.mkdir(parents=True)
                (dist / "index.html").write_text("<h1>Shelter fixture</h1>")
                if provider == "azure":
                    package = next(
                        step["bash"] for step in source["BuildClient"]["steps"]
                        if step.get("name") == "package"
                    )
                    produced = root / "staging/pets-build"
                    variables = {
                        "BUILD_DIRECTORY": str(produced),
                        "BUILD_SOURCEVERSION": sha,
                        "BUILD_ARTIFACT_NAME": "pets-migration-build-101-1-1",
                    }
                    verify = source["Verify"]["steps"][-1]["bash"]
                    expected_key = "BUILD_SOURCEVERSION"
                else:
                    package = next(
                        step["run"] for step in target["jobs"]["build-client"]["steps"]
                        if "tar -czf" in step.get("run", "")
                    )
                    produced = root / "pets-migration-build"
                    variables = {"GITHUB_SHA": sha}
                    verify = target["jobs"]["verify"]["steps"][-1]["run"]
                    expected_key = "EXPECTED_SHA"
                result = run_step(package, root, **variables)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    {file.name for file in produced.iterdir()},
                    {"site.tar.gz", "commit.txt", "SHA256SUMS"},
                )
                if provider == "azure":
                    self.assertIn(
                        "variable=artifactName;isOutput=true]pets-migration-build-101-1-1",
                        result.stdout,
                    )
                consumer = root / "consumer"
                shutil.copytree(produced, consumer)
                variables = {expected_key: sha, "GITHUB_STEP_SUMMARY": str(root / "summary")}
                result = run_step(verify, consumer, **variables)
                self.assertEqual(result.returncode, 0, result.stderr)
                with (consumer / "site.tar.gz").open("ab") as archive:
                    archive.write(b"tampering")
                self.assertNotEqual(run_step(verify, consumer, **variables).returncode, 0)
                shutil.copyfile(produced / "site.tar.gz", consumer / "site.tar.gz")
                self.assertNotEqual(
                    run_step(verify, consumer, **{**variables, expected_key: "b" * 40}).returncode, 0
                )
                (consumer / "SHA256SUMS").unlink()
                self.assertNotEqual(run_step(verify, consumer, **variables).returncode, 0)

    def test_azure_collects_only_existing_browser_diagnostics(self):
        _, source, _ = migration()
        collect = source["TestE2E"]["steps"][-2]["bash"]
        for has_report in (False, True):
            with self.subTest(has_report=has_report):
                root = self.workspace / str(has_report)
                root.mkdir()
                if has_report:
                    report = root / "app/client/playwright-report"
                    report.mkdir(parents=True)
                    (report / "index.html").write_text("<html>report fixture</html>")
                    trace = root / "app/client/test-results"
                    trace.mkdir()
                    (trace / "trace.zip").write_bytes(b"trace fixture")
                    (root / "app/client/private.db").write_bytes(b"must not be copied")
                saved = root / "saved"
                result = run_step(collect, root, REPORT_DIRECTORY=str(saved))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    f"variable=hasBrowserReport]{str(has_report).lower()}", result.stdout
                )
                if has_report:
                    self.assertEqual(
                        {file.name for file in saved.iterdir()}, {"playwright-report", "test-results"}
                    )
                else:
                    self.assertEqual(list(saved.iterdir()), [])
                    self.assertIn("type=warning", result.stdout)


if __name__ == "__main__":
    unittest.main()
