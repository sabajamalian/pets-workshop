"""Validate local workshop links and the opt-in workflow examples."""

import argparse
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
        snapshots[path] = document
        errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in workflow_errors(document))
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
