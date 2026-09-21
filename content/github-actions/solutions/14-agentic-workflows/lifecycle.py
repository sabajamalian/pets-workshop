"""A fixed, model-free Pets validation lifecycle. Goals never select commands."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import unittest

SOURCE_FILES = (
    "app.py",
    "test_app.py",
    "models/__init__.py",
    "models/base.py",
    "models/breed.py",
    "models/dog.py",
)
AUDIT_FILES = {"plan.json", "result.json", "observation.txt", "verdict.json"}
LOG_LIMIT = 131072
TEST_TIMEOUT = 90


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n")


def git(checkout, *args):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], stderr=subprocess.STDOUT, timeout=15
    )


def is_clean(checkout):
    return not git(
        checkout, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"
    )


def regular_file(root, relative):
    path = root / relative
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise ValueError("Symlinks are not allowed")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Expected a regular allowlisted file")
    return path


def good_result(result):
    counts = (
        "tests_run", "failures", "errors", "skipped",
        "expected_failures", "unexpected_successes",
    )
    return (
        isinstance(result, dict)
        and set(result) == {*counts, "successful"}
        and all(type(result[key]) is int and result[key] >= 0 for key in counts)
        and result["tests_run"] > 0
        and all(result[key] == 0 for key in counts if key != "tests_run")
        and result["successful"] is True
    )


def test_worker(context, result_path):
    resource.setrlimit(resource.RLIMIT_FSIZE, (LOG_LIMIT, LOG_LIMIT))
    os.environ["DATABASE_PATH"] = ":memory:"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(context))
    suite = unittest.defaultTestLoader.loadTestsFromName("test_app")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "successful": result.wasSuccessful(),
    }
    write_json(result_path, report)
    return 0 if good_result(report) else 1


def run_action(python, context, result_path, observation):
    environment = {
        "PATH": os.defpath,
        "HOME": str(context.parent / "home"),
        "DATABASE_PATH": ":memory:",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    with observation.open("wb") as output:
        try:
            result = subprocess.run(
                [str(python), "-I", "-B", str(Path(__file__).resolve()),
                 "_test", str(context), str(result_path)],
                cwd=context, env=environment, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT, timeout=TEST_TIMEOUT,
                check=False,
            )
            return result.returncode if result.returncode >= 0 else 1
        except subprocess.TimeoutExpired:
            return 124


def simulate(checkout, work, python):
    checkout, work, python = checkout.resolve(), work.resolve(), python.absolute()
    if work.is_relative_to(checkout) or checkout.is_relative_to(work):
        raise ValueError("Work directory must be separate from the checkout")
    if python.is_relative_to(checkout):
        raise ValueError("Use a Python environment outside the checkout")
    work.mkdir(parents=True, exist_ok=False)
    audit = work / "audit"
    audit.mkdir()
    observation = audit / "observation.txt"
    observation.write_text("Action not started.\n")
    goal = os.environ.get("UNTRUSTED_GOAL", "")
    source_sha = git(checkout, "rev-parse", "HEAD").decode().strip()
    plan = {
        "schema": 1, "source_sha": source_sha,
        "goal": goal if 1 <= len(goal) <= 200 else "[rejected length]",
        "context": list(SOURCE_FILES),
        "action": "Load test_app with unittest and run once",
        "iteration_budget": 1, "timeout_seconds": TEST_TIMEOUT,
        "model": None,
    }
    write_json(audit / "plan.json", plan)
    write_json(audit / "result.json", {})
    code, reason, clean = 1, "Intake rejected", False
    try:
        if not 1 <= len(goal) <= 200:
            raise ValueError("Goal must contain 1 to 200 characters")
        if not is_clean(checkout):
            raise ValueError("Checkout must start clean, including ignored paths")
        context = work / "context"
        context.mkdir()
        (work / "home").mkdir()
        for relative in SOURCE_FILES:
            source = regular_file(checkout / "app/server", relative)
            target = context / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        code = run_action(python, context, audit / "result.json", observation)
        reason = "Tests passed" if code == 0 else "Test execution failed or timed out"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        reason = str(error)
    finally:
        try:
            clean = is_clean(checkout)
        except subprocess.SubprocessError:
            clean = False
    result = json.loads((audit / "result.json").read_text())
    accepted = code == 0 and good_result(result) and clean
    write_json(audit / "verdict.json", {
        "schema": 1, "source_sha": source_sha,
        "test_exit_code": code, "checkout_clean": clean,
        "accepted": accepted, "reason": reason,
    })
    write_json(audit / "manifest.json", {
        name: hashlib.sha256((audit / name).read_bytes()).hexdigest()
        for name in sorted(AUDIT_FILES)
    })
    print("Simulation accepted." if accepted else "Simulation rejected; inspect the audit.")
    return 0 if accepted else (code if 1 <= code <= 125 else 1)


def verify_audit(directory, expected_sha):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Expected an audit directory")
    if {item.name for item in directory.iterdir()} != AUDIT_FILES | {"manifest.json"}:
        raise ValueError("Missing or unexpected audit files")
    for name in AUDIT_FILES | {"manifest.json"}:
        path = regular_file(directory, name)
        limit = LOG_LIMIT if name == "observation.txt" else 16384
        if not 0 < path.stat().st_size <= limit:
            raise ValueError("Empty or oversized audit file")
    manifest = json.loads((directory / "manifest.json").read_text())
    if not isinstance(manifest, dict) or set(manifest) != AUDIT_FILES:
        raise ValueError("Invalid manifest")
    for name in AUDIT_FILES:
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != manifest[name]:
            raise ValueError("Audit checksum mismatch")
    plan = json.loads((directory / "plan.json").read_text())
    verdict = json.loads((directory / "verdict.json").read_text())
    result = json.loads((directory / "result.json").read_text())
    if not isinstance(plan, dict) or not isinstance(verdict, dict):
        raise ValueError("Invalid audit objects")
    if (
        plan.get("schema") != 1 or plan.get("source_sha") != expected_sha
        or not isinstance(plan.get("goal"), str) or not 1 <= len(plan["goal"]) <= 200
        or plan.get("context") != list(SOURCE_FILES)
        or plan.get("action") != "Load test_app with unittest and run once"
        or plan.get("iteration_budget") != 1 or plan.get("model", "missing") is not None
        or plan.get("timeout_seconds") != TEST_TIMEOUT
        or verdict.get("schema") != 1 or verdict.get("source_sha") != expected_sha
        or type(verdict.get("test_exit_code")) is not int
        or verdict["test_exit_code"] != 0
        or verdict.get("checkout_clean") is not True
        or verdict.get("accepted") is not True or not good_result(result)
    ):
        raise ValueError("Audit does not meet the deterministic acceptance policy")
    print("Audit verified. No repository write or deployment is authorized.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("simulate")
    run.add_argument("--checkout", type=Path, required=True)
    run.add_argument("--work-dir", type=Path, required=True)
    run.add_argument("--python", type=Path, default=Path(sys.executable))
    audit = commands.add_parser("audit")
    audit.add_argument("--directory", type=Path, required=True)
    audit.add_argument("--expected-sha", required=True)
    worker = commands.add_parser("_test")
    worker.add_argument("context", type=Path)
    worker.add_argument("result", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "simulate":
            return simulate(args.checkout, args.work_dir, args.python)
        if args.command == "_test":
            return test_worker(args.context, args.result)
        verify_audit(args.directory, args.expected_sha)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
