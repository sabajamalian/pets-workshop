"""Validate local workshop links and the opt-in workflow examples."""

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


TRACK = Path(__file__).resolve().parents[1]
ROOT = TRACK.parents[1]
PIN = re.compile(r"^[\w.-]+/[\w./-]+@[a-f0-9]{40}$")
DEFINITION = re.compile(r"^\[([^\]]+)\]:\s*(\S+)", re.MULTILINE)
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REFERENCE = re.compile(r"!?\[[^\]\n]+\]\[([^\]\n]+)\]")
AGENTIC_STAGE = "14-agentic-workflows"
AGENTIC_COMPILER = "v0.88.8"


def solution_kind(path):
    """Only designated foreign/generated examples use a different contract."""
    if path.parent.name == "16-migration" and path.name == "azure-pipelines.yml":
        return "azure"
    if path.parent.name == AGENTIC_STAGE and path.name == "pets-test-plan.lock.yml":
        return "agentic"
    return "actions"


def agentic_source(path):
    sections = path.read_text().split("---", 2)
    if len(sections) != 3 or sections[0].strip():
        raise ValueError("agentic source must start with YAML frontmatter")
    return yaml.load(sections[1], Loader=yaml.BaseLoader)


def agentic_errors(path, document):
    """Check lab policy; check_agentic.py verifies compilation and freshness."""
    errors = []
    source_path = path.with_name("pets-test-plan.md")
    if not source_path.exists():
        return ["compiled agentic workflow is missing its Markdown source"]
    try:
        source = agentic_source(source_path)
        metadata_line = path.read_text().splitlines()[0]
        prefix = "# gh-aw-metadata: "
        if not metadata_line.startswith(prefix):
            return ["missing compiler metadata"]
        metadata = json.loads(metadata_line.removeprefix(prefix))
    except (ValueError, yaml.YAMLError, IndexError) as error:
        return [f"invalid agentic source or metadata: {error}"]
    if not isinstance(source, dict) or not isinstance(metadata, dict) or not isinstance(document, dict):
        return ["expected agentic source, metadata, and lock mappings"]
    if metadata.get("compiler_version") != AGENTIC_COMPILER:
        errors.append(f"expected compiler {AGENTIC_COMPILER}; review source and lock together")
    if source.get("engine") != "copilot" or source.get("strict") != "true":
        errors.append("agentic example must use the Copilot engine in strict mode")
    triggers = source.get("on", {})
    if set(triggers) != {"workflow_dispatch", "roles", "manual-approval", "reaction", "status-comment"}:
        errors.append("agentic example must remain manual-only")
    if triggers.get("manual-approval") != "pets-agentic":
        errors.append("agentic activation must require pets-agentic")
    if source.get("permissions") != {"contents": "read"}:
        errors.append("personal-fork agent must have only contents: read")
    if source.get("checkout") != "false" or source.get("network") != "defaults":
        errors.append("agent checkout must be disabled and network must use defaults")
    tools = source.get("tools", {})
    if set(tools) != {"bash", "edit", "cli-proxy", "github"} or any(
        tools.get(key) != "false" for key in ("bash", "edit", "cli-proxy")
    ):
        errors.append("agent must not gain shell, edit, CLI proxy, or additional tools")
    expected_github = {
        "mode": "local", "toolsets": ["repos"], "read-only": "true",
        "allowed-repos": "${{ github.repository }}", "min-integrity": "approved",
        "allowed": [{"name": "get_file_contents", "max-calls": "4"}],
    }
    if tools.get("github") != expected_github:
        errors.append("agent GitHub tools must retain the bounded file-reading policy")
    expected_outputs = {
        "staged": "true", "report-failed-jobs": "false",
        "threat-detection": {"max-ai-credits": "50"},
        "create-issue": {"title-prefix": "[Pets test plan] ", "max": "1", "expires": "false"},
    }
    if source.get("safe-outputs") != expected_outputs:
        errors.append("safe outputs must remain staged, bounded, and threat-detected")
    for key, expected in {"timeout-minutes": "5", "max-ai-credits": "100", "max-turns": "8"}.items():
        if source.get(key) != expected:
            errors.append(f"agentic example must retain {key}: {expected}")
    guard = "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
    if source.get("if") != guard:
        errors.append("agent must remain restricted to the default branch")
    jobs = document.get("jobs", {})
    if set(jobs) != {"pre_activation", "activation", "agent", "detection", "safe_outputs", "conclusion"}:
        errors.append("unexpected compiler jobs; review generated workflow")
    if set(document.get("on", {})) != {"workflow_dispatch"} or document.get("permissions") != {}:
        errors.append("compiled workflow must remain manual with no top-level permissions")
    if jobs.get("activation", {}).get("environment") != "pets-agentic":
        errors.append("compiled activation must retain approval")
    if jobs.get("pre_activation", {}).get("if") != guard:
        errors.append("compiled workflow must check the default branch before activation")
    agent = jobs.get("agent", {})
    if agent.get("permissions") != {"contents": "read"} or agent.get("needs") != "activation":
        errors.append("compiled agent must remain read-only and depend on activation")
    if agent.get("timeout-minutes") != "15" or jobs.get("detection", {}).get("timeout-minutes") != "5":
        errors.append("compiled agent/detection timeouts changed")
    safe = jobs.get("safe_outputs", {})
    if safe.get("permissions") != {} or safe.get("env", {}).get("GH_AW_SAFE_OUTPUTS_STAGED") != "true":
        errors.append("compiled safe outputs must be staged without write scopes")
    for name, job in jobs.items():
        for permission, level in job.get("permissions", {}).items():
            if level == "write" and not (name == "conclusion" and permission in {"actions", "issues"}):
                errors.append(f"{name}: unexpected compiled write permission: {permission}")
        for step in job.get("steps", []):
            action = step.get("uses", "")
            if action and not PIN.fullmatch(action):
                errors.append(f"{name}: compiled action is not pinned: {action}")
            if action.startswith("actions/checkout@") and step.get("with", {}).get("persist-credentials") != "false":
                errors.append(f"{name}: compiled checkout must not persist credentials")
    return errors


def azure_errors(document):
    if not isinstance(document, dict):
        return ["expected an Azure Pipelines mapping"]
    errors = []
    if document.get("trigger") != "none" or document.get("pr") != "none":
        errors.append("migration source must keep trigger and pr disabled")
    if any(key in document for key in ("on", "permissions")):
        errors.append("Azure source must not be treated as an Actions workflow")
    jobs = list(document.get("jobs", []))
    for stage in document.get("stages", []):
        jobs.extend(stage.get("jobs", []))
    if not jobs:
        errors.append("Azure migration source has no jobs")
    for job in jobs:
        if not isinstance(job, dict):
            errors.append("Azure jobs must be mappings in a list")
            continue
        name = job.get("job", "<unnamed>")
        timeout = job.get("timeoutInMinutes", "")
        if not str(timeout).isdigit() or not 1 <= int(timeout) <= 30:
            errors.append(f"{name}: expected Azure timeoutInMinutes from 1 to 30")
        if "deployment" in job:
            errors.append("migration lab must not deploy")
    return errors


def markdown_errors(path):
    text = path.read_text()
    # Ignore examples containing literal Markdown, shell strings, or expressions.
    prose = re.sub(r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$", "", text)
    definitions = {key.casefold(): value for key, value in DEFINITION.findall(prose)}
    errors = []
    for label in REFERENCE.findall(prose):
        if label.casefold() not in definitions:
            errors.append(f"{path.relative_to(ROOT)}: undefined reference [{label}]")
    targets = list(definitions.values()) + INLINE_LINK.findall(prose)
    for target in targets:
        url = urlsplit(target.strip("<>"))
        if url.scheme or url.netloc:
            continue
        relative = unquote(url.path)
        destination = ROOT / relative.lstrip("/") if relative.startswith("/") else path.parent / relative
        if not relative:
            destination = path
        if not destination.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target {target}")
        elif url.fragment and destination.suffix == ".md":
            headings = re.findall(r"^#{1,6}\s+(.+)$", destination.read_text(), re.MULTILINE)
            slugs = set()
            counts = {}
            for heading in headings:
                slug = re.sub(r"[^\w\s-]", "", heading.lower()).strip().replace(" ", "-")
                count = counts.get(slug, 0)
                counts[slug] = count + 1
                slugs.add(f"{slug}-{count}" if count else slug)
            if unquote(url.fragment) not in slugs:
                errors.append(f"{path.relative_to(ROOT)}: missing heading {target}")
    return errors


def workflow_errors(document):
    """Check teaching invariants, not a general workflow security policy."""
    errors = []
    if not isinstance(document, dict):
        return ["expected a YAML mapping"]
    if "runs" in document:
        jobs = {"action": {"steps": document["runs"].get("steps", [])}}
    else:
        if document.get("permissions", {}).get("contents") != "read":
            errors.append("workflow must declare contents: read")
        triggers = document.get("on", {})
        if "pull_request_target" in triggers:
            errors.append("examples must not execute privileged pull_request_target workflows")
        jobs = document.get("jobs", {})
        if not jobs:
            errors.append("workflow has no jobs")
    for name, job in jobs.items():
        if "runs-on" in job:
            timeout = job.get("timeout-minutes", "")
            if not str(timeout).isdigit() or not 1 <= int(timeout) <= 30:
                errors.append(f"{name}: expected timeout-minutes from 1 to 30")
        if job.get("permissions", {}).get("contents") == "write":
            errors.append(f"{name}: examples must not grant repository write permission")
        for step in job.get("steps", []):
            action = step.get("uses", "")
            if action and not action.startswith("./") and not PIN.fullmatch(action):
                errors.append(f"{name}: action is not pinned to a full SHA: {action}")
            options = step.get("with", {})
            if action.startswith("actions/checkout@") and options.get("persist-credentials") != "false":
                errors.append(f"{name}: checkout must disable persisted credentials")
            if action.startswith("actions/setup-node@") and options.get("node-version") != "22":
                errors.append(f"{name}: expected the shared Node 22 runtime")
            if action.startswith("actions/upload-artifact@"):
                retention = options.get("retention-days", "")
                if not str(retention).isdigit() or not 1 <= int(retention) <= 30:
                    errors.append(f"{name}: artifact retention must be explicit and bounded")
            if re.search(r"\$\{\{\s*(inputs\.|github\.event\.)", step.get("run", "")):
                errors.append(f"{name}: pass untrusted expressions through env, not run")
    return errors


def snippet_errors(path, examples):
    errors = []
    fences = re.findall(r"(?ms)^[ \t]*```ya?ml[ \t]*\n(.*?)^[ \t]*```[ \t]*$", path.read_text())
    for snippet in fences:
        try:
            document = yaml.load(textwrap.dedent(snippet), Loader=yaml.BaseLoader)
        except yaml.YAMLError as error:
            errors.append(f"{path.relative_to(ROOT)}: invalid YAML example: {error}")
            continue
        if not isinstance(document, dict):
            continue
        complete_workflow = all(key in document for key in ("name", "on", "jobs"))
        complete_action = all(key in document for key in ("name", "runs"))
        if (complete_workflow or complete_action) and document not in examples:
            errors.append(f"{path.relative_to(ROOT)}: complete YAML example has no matching solution")
    return errors


def reference_errors(document, snapshots):
    errors = []
    calls = []
    for name, job in document.get("jobs", {}).items():
        calls.append((name, job, True))
        calls.extend((name, step, False) for step in job.get("steps", []))
    for name, call, is_workflow in calls:
        reference = call.get("uses", "")
        if not reference.startswith("./"):
            continue
        if is_workflow:
            suffix = "/" + Path(reference).name
            candidates = [data for path, data in snapshots.items() if path.as_posix().endswith(suffix)]
            schemas = [data.get("on", {}).get("workflow_call", {}).get("inputs", {}) for data in candidates]
        else:
            suffix = "/" + reference.removeprefix("./.github/actions/") + "/action.yml"
            candidates = [data for path, data in snapshots.items() if path.as_posix().endswith(suffix)]
            schemas = [data.get("inputs", {}) for data in candidates]
        if not schemas:
            errors.append(f"{name}: no solution companion for {reference}")
            continue
        supplied = call.get("with", {})
        schema = schemas[-1]
        unknown = set(supplied) - set(schema)
        missing = {
            key for key, spec in schema.items()
            if spec.get("required") == "true" and "default" not in spec and key not in supplied
        }
        if unknown or missing:
            errors.append(f"{name}: {reference} input mismatch; unknown={sorted(unknown)}, missing={sorted(missing)}")
    return errors


def check(track=TRACK):
    errors = []
    examples = []
    snapshots = {}
    for path in sorted(track.rglob("*.md")):
        errors.extend(markdown_errors(path))
    for path in (ROOT / "README.md", ROOT / "content/README.md"):
        errors.extend(markdown_errors(path))
    for path in sorted((track / "solutions").rglob("*.yml")):
        try:
            # BaseLoader preserves the Actions key "on" and yields string scalars.
            document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        except yaml.YAMLError as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
            continue
        examples.append(document)
        kind = solution_kind(path)
        if kind == "azure":
            findings = azure_errors(document)
        elif kind == "agentic":
            findings = agentic_errors(path, document)
        else:
            snapshots[path] = document
            findings = workflow_errors(document)
        errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in findings)
    for path, document in snapshots.items():
        errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in reference_errors(document, snapshots))
    for path in sorted(track.glob("*.md")):
        errors.extend(snippet_errors(path, examples))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = check()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Workshop links and solution invariants passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
