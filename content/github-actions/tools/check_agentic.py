"""Recompile the opt-in gh-aw example in a temporary repo and detect stale locks."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from check_workshop import AGENTIC_COMPILER, AGENTIC_STAGE, TRACK


def check(compiler):
    version = subprocess.run(
        [*compiler, "version"], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=30
    ).stdout.strip()
    if version != f"gh aw version {AGENTIC_COMPILER}":
        raise ValueError(f"expected gh-aw {AGENTIC_COMPILER}, got {version!r}")
    stage = TRACK / "solutions" / AGENTIC_STAGE
    with tempfile.TemporaryDirectory(prefix="pets-gh-aw-") as directory:
        root = Path(directory)
        workflows = root / ".github/workflows"
        cache = root / ".github/aw"
        workflows.mkdir(parents=True)
        cache.mkdir()
        for name in ("pets-test-plan.md", "pets-test-plan.lock.yml"):
            shutil.copyfile(stage / name, workflows / name)
        shutil.copyfile(stage / "actions-lock.json", cache / "actions-lock.json")
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, timeout=30)
        subprocess.run(
            [*compiler, "compile", "pets-test-plan", "--strict", "--no-check-update"],
            cwd=root, check=True, timeout=180,
        )
        if (stage / "pets-test-plan.lock.yml").read_bytes() != (workflows / "pets-test-plan.lock.yml").read_bytes():
            raise ValueError("stale agentic lockfile: recompile from .github/workflows and review the diff")
        if (stage / "actions-lock.json").read_bytes() != (cache / "actions-lock.json").read_bytes():
            raise ValueError("stale action pins: review regenerated .github/aw/actions-lock.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, help="Pinned standalone gh-aw binary; defaults to gh aw")
    args = parser.parse_args()
    compiler = [str(args.compiler.resolve())] if args.compiler else ["gh", "aw"]
    try:
        check(compiler)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Agentic validation failed: {error}", file=sys.stderr)
        return 1
    print("Agentic source compiles and matches the inactive lockfile and action pins. No workflow was run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
