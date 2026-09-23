# Copilot CLI with a Protected, Read-Only Report

| [Previous: Protected environments][walkthrough-previous] | [Next: Agentic workflows][walkthrough-next] |
|:------------------------------------------------------|------------------------------------------------------:|

## Scenario

A new shelter volunteer wants to understand how the Flask API lists dogs and
returns a dog's details. You want to offer a short explanation without letting
an AI tool edit the application, run commands, or publish changes.

Start with a deterministic report that needs no Copilot installation, model,
subscription, or AI credential. A separate, optional job demonstrates an actual
Copilot CLI explanation only after an owner configures protection and a reviewer
approves the run.

## Background

Copilot CLI is an agentic command-line tool, not a replacement for the shelter's
unit tests. An explanation can be wrong. Repository comments can contain hostile
instructions. Generated output is untrusted text, never a command, a test result,
or permission to deploy.

This exercise uses the real [`app/server/app.py`][pets-api]. Its `get_dogs`
function implements listing and pagination. Its `get_dog` function handles dog
details and missing dogs. The report context is only that file. It excludes the
shelter database, model package, volunteer information, repository instructions,
Git metadata, and the rest of the application. The dry run parses Python syntax;
it does not import Flask or initialize a database.

### Two deliberately separate paths

| Path | What happens | What it needs |
|------|--------------|---------------|
| `dry_run: true`, the default | Python produces a fixed Pets review checklist and source checksum | Actions access, no AI credentials |
| `dry_run: false`, optional | An approved job installs a pinned CLI and asks for one read-only explanation | Configured environment, eligible Copilot access, owner-approved authentication and usage |

Both paths use manual dispatch on the default branch, read-only repository
permissions, exact run-SHA checkout, and finite job timeouts. Neither runs on PRs,
issues, comments, or deployment events. Do not add `pull_request_target`.

### Verified CLI contract

The example was checked against official documentation on **2026-09-21**:

- The supported npm package is `@github/copilot`; the example pins
  **1.0.87**, which has an [official release][cli-release]. The source workshop's
  earlier version is not a compatibility guarantee. npm installation needs
  **Node.js 22 or later**; this job selects Node.js 22.
- The [runtime manifest][cli-manifest] and [reviewed lockfile][cli-lock] pin the
  CLI's transitive and platform-specific dependencies with integrity hashes.
  The approved job copies both outside the checkout and uses `npm ci
  --ignore-scripts`, so it doesn't resolve fresh dependency ranges or run package
  lifecycle scripts. A version upgrade requires reviewing the entire lockfile.
  The lock omits registry-specific download URLs using npm's
  `--omit-lockfile-registry-resolved` option; the exact versions and integrity
  hashes still apply when npm fetches from the runner's configured registry.
- A personal-account-owned, fine-grained PAT with the **Copilot Requests**
  account permission is a [supported authentication method][cli-auth]. A
  classic PAT is not supported. This example uses an environment-scoped PAT,
  not a repository secret or a token saved by interactive login.
- Current official guidance also supports the Actions `GITHUB_TOKEN` with
  **`copilot-requests: write`** and applicable organization policy. That
  permission is absent from this example's default `contents: read` token.
  [Token-based Actions authentication][cli-actions-token] is an alternative
  design to review separately, not an automatic fallback on failure.
- The documented [tool controls][cli-tools] separate tool availability from
  tool permission. `view` is the only available tool; read access is allowed,
  and shell and write operations are explicitly denied.
- The [command reference][cli-reference] documents the controls that disable
  built-in MCP servers, custom instructions, broad temporary-directory access,
  automatic updates, and follow-up questions. The helper checks the installed
  version and required flags before passing authentication to the CLI.

The CLI still communicates with the approved model service. Read-only tool
permissions are not a network sandbox or an OS security boundary. Use fresh
GitHub-hosted runners and only reviewed, non-sensitive source. The CLI binary,
package installation, workflow, and helper remain trusted code.

## 1. Install the opt-in example

1. Review the [complete workflow][solution-workflow] and
   [report helper][solution-helper].
2. Copy only `copilot-cli.yml` to `.github/workflows/copilot-cli.yml` in your
   workshop repository.
3. Keep `report.py` and `runtime/package.json` plus `runtime/package-lock.json`
   under `content/github-actions/solutions/13-copilot-cli/`.
   The workflow uses them from those locations. `test_report.py` is an optional
   local regression check, not a required workflow companion.
4. Have the workflow, helper, and runtime lockfile reviewed through your normal change process
   before installing them on the default branch. A workflow-dispatch file must
   exist there to appear in the Actions UI.

The critical input and permission settings are:

```yaml
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: Do not install or call Copilot CLI
        required: true
        default: true
        type: boolean

permissions:
  contents: read
```

Do not copy the entire solutions tree into `.github/workflows`. These solution
files are inactive until you install the named workflow.

## 2. Run the credential-free path

1. Open **Actions**, select **Pets Copilot CLI**, and choose **Run workflow**.
2. Select the default branch and leave **dry_run** checked.
3. Inspect the `dry-run` job. `approved-cli` should be skipped, so no Node
   setup, npm install, AI secret reference, or model call runs.
4. Download `pets-copilot-dry-<run-id>-<attempt>`. Read `report.txt` and
   `metadata.json`. The latter must say `"model_called": false`.

Expected outcome: a fixed checklist naming the two Flask handler functions and
a SHA-256 of the source. The checksum records which file was examined. It does
not prove the explanation is correct or establish cryptographic provenance.

You can check the helper without GitHub or network access:

Use Linux, macOS, or WSL for these local helper tests. The output limit uses
Python's `resource` module and `RLIMIT_FSIZE`, which native Windows does not
provide. The hosted workflow uses `ubuntu-latest`.

```bash
PYTHONDONTWRITEBYTECODE=1 python3.13 -B -m unittest discover \
  -s content/github-actions/solutions/13-copilot-cli -p 'test_*.py' -v
```

These tests use local fixture directories within the stage, mock the live CLI
boundary, and remove their fixtures. They do not install or invoke Copilot.

## 3. Have an owner configure the optional live environment

Skip this section if real AI usage has not been authorized. The dry-run learning
outcome is complete without it.

1. A repository owner or administrator creates **`pets-copilot`** in
   **Settings > Environments** before any live run.
2. Configure **Required reviewers**, enable **Prevent self-review**, and
   disable administrator bypass where supported. A different reviewer must be
   available. Only one of the configured reviewers needs to approve a job.
3. Under **Deployment branches and tags**, choose **Selected branches and
   tags** and add a **Branch** rule for the exact default branch, usually
   `main`. Do not add tag rules or wildcard branches. Update this rule if the
   default branch changes. The workflow also checks the default-branch ref.
4. Confirm feature availability against the [environment documentation][environments]
   and [protection-rule reference][environment-rules]. Free plans support
   environments in public repositories. Pro and Team also support private
   environments, but required reviewers on Free, Pro, and Team are available
   only for public repositories. For private/internal review gates, confirm
   applicable Enterprise support before proceeding.
5. Confirm active Copilot access, organization policies, approved model access
   to `claude-haiku-4.5`, billing responsibility, budgets, and permission to
   send the reviewed `app.py` to the service.
6. The authorized token owner creates a short-lived, fine-grained PAT owned by
   their **personal account**, with **Copilot Requests** under account
   permissions. Choose the minimum repository access and no repository write
   permissions. Store it only as environment secret **`PETS_COPILOT_TOKEN`**
   in `pets-copilot`. Do not put it in code, form inputs, artifacts, or logs.

> [!IMPORTANT]
> Referencing a nonexistent environment can create it without protection.
> Merely writing `environment: pets-copilot` does not configure approval.
> If reviewers or prevention of self-review are unavailable, keep the live
> path off and discuss its logs as a walkthrough. Removing the gate is not
> an equivalent exercise.

The PAT authorizes model requests separately from the workflow's read-only
`GITHUB_TOKEN`. Usage is attributed to the PAT owner's Copilot seat. An Actions
job timeout, a two-minute CLI subprocess timeout, one prompt, and a 16 KiB
captured-response limit constrain execution, but are **not exact cost caps**.
One prompt can require more than one model request. Configure actual billing
controls and monitor usage separately.

## 4. Inspect the live boundary before approving it

Review the job condition in the complete solution:

```yaml
if: >-
  !inputs.dry_run &&
  github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
environment: pets-copilot
```

The helper creates a fresh directory under `RUNNER_TEMP`, copies only `app.py`
into a separate context directory, and starts the CLI from that directory.
It uses a new `HOME`, `COPILOT_HOME`, and XDG configuration directory, with an
explicit environment allowlist. It does not forward ambient GitHub tokens,
provider keys, plugin configuration, or checkout credentials.

The CLI installation step receives no Copilot token and uses the checked-in
lockfile. Missing or inconsistent lockfiles and integrity failures stop that job;
don't replace `npm ci` with `npm install` to bypass them. The token is supplied
only to the subsequent report step. Locking dependencies makes installation
reproducible; it doesn't establish that the reviewed package code is trustworthy.

The reviewed restriction arguments are:

```text
--available-tools=view --allow-tool=read
--deny-tool=shell --deny-tool=write
--disable-builtin-mcps --no-custom-instructions --disallow-temp-dir
--no-auto-update --no-ask-user --log-level=none --stream=off
```

The fixed prompt requests an explanation, not edits. Permission controls, not
that wording, remove shell/write capabilities. Fresh configuration prevents
loading user-configured MCP servers; the explicit flag disables built-in MCP
servers. There are no custom agents or repository instructions in context.

If separately authorized, uncheck **dry_run**, run on the default branch, and
ask the independent reviewer to inspect the workflow SHA and context before
approval. Missing credentials, a mismatched version, unsupported restrictions,
timeout, empty/oversized output, or context mutations fail closed. Do not
remove a restriction to make a failed run green.

Only `report.txt` and `metadata.json` are published, retained for seven days.
Raw diagnostics, CLI configuration, home directories, and session state are
not uploaded. The job summary is fixed text, never raw model output. Read
the downloaded explanation as untrusted text; do not execute, source, evaluate,
or paste it into a privileged command. It does not gate tests or deployment.

## 5. Break, diagnose, and fix without a paid call

1. Run the local regression command from section 2.
2. Inspect `test_missing_restrictions_or_wrong_version_fail_before_model`.
   It substitutes a CLI that reports an unsupported version or omits required
   flags. The helper rejects it before the mocked model invocation.
3. Inspect `test_context_mutation_rejected`. An unexpected file appears in the
   isolated context, so no report is published.
4. For a controlled exercise, make the expected flag or unexpected-file name
   different in your local fixture, observe the test failure, then restore it.
   Keep all changes inside this stage's test file, not the actual API.
5. Diagnose missing `PETS_COPILOT_TOKEN` as an owner setup problem. Never fall
   back to a classic PAT, ambient `gh` login, permissive tools, or automatic
   model calls.

After an authorized live demonstration, revoke the demonstration PAT and remove
its environment secret. Keep `dry_run: true` as the default.

## Summary and next steps

You now have a credential-free report and a separately approved example of a
minimal-context CLI call. You can distinguish the prompt from the permission
boundary and recognize generated prose as untrusted output.

Next, [author a GitHub Agentic Workflow][walkthrough-next] with Markdown,
`gh aw` compilation, and staged safe outputs. Compilation is credential-free;
the separately approved execution uses a real AI engine.

## Resources

- [Complete Copilot workflow][solution-workflow]
- [Report helper][solution-helper] and [offline boundary tests][solution-tests]
- [Runtime manifest][cli-manifest] and [dependency lockfile][cli-lock]
- [Installing Copilot CLI][cli-install]
- [Authenticating Copilot CLI][cli-auth]
- [Command reference][cli-reference] and [programmatic reference][cli-programmatic]
- [Tool permissions and availability][cli-tools]
- [Actions token authentication][cli-actions-token] and [billing considerations][cli-billing]
- [Managing environments][environments]
- [Source workshop CLI exercise][source-lesson], adapted for the Pets API

| [Previous: Protected environments][walkthrough-previous] | [Next: Agentic workflows][walkthrough-next] |
|:------------------------------------------------------|------------------------------------------------------:|

[walkthrough-previous]: 12-protected-environments.md
[walkthrough-next]: 14-agentic-workflows.md
[pets-api]: ../../app/server/app.py
[solution-workflow]: solutions/13-copilot-cli/copilot-cli.yml
[solution-helper]: solutions/13-copilot-cli/report.py
[solution-tests]: solutions/13-copilot-cli/test_report.py
[cli-manifest]: solutions/13-copilot-cli/runtime/package.json
[cli-lock]: solutions/13-copilot-cli/runtime/package-lock.json
[cli-release]: https://github.com/github/copilot-cli/releases/tag/v1.0.87
[cli-install]: https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli
[cli-auth]: https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli
[cli-reference]: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
[cli-programmatic]: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference
[cli-tools]: https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools
[cli-actions-token]: https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions
[cli-billing]: https://docs.github.com/en/copilot/concepts/agents/copilot-cli/copilot-cli-in-github-actions
[environments]: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
[environment-rules]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
[source-lesson]: https://github.com/sabajamalian/workshop-github-action/tree/main/workshop/05-github-copilot-cli
