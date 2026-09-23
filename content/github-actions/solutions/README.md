# Complete Workshop Solutions

These files are references for the [GitHub Actions workshop][workshop]. They are
deliberately outside `.github/workflows`, so they do not run when you create a
repository from the template.

## Install one stage at a time

Read the matching lesson first. Copy only the files it names and review changes
before committing them. Later core stages update earlier workflows rather than
installing a second copy under a different filename.

| Stage | Destination or dependency |
| --- | --- |
| [01: Introduction](01-introduction/) | Install `hello.yml` as `.github/workflows/hello.yml`. |
| [03: Tests](03-running-tests/) | Install `run-tests.yml` as `.github/workflows/run-tests.yml`. |
| [04: Caching](04-caching/) | Replace the preceding `run-tests.yml`. |
| [05: Matrix](05-matrix/) | Replace the preceding `run-tests.yml`. |
| [06: Azure](06-deploy-azure/) | Install `azure-dev.yml`; first complete the Azure and OIDC setup in lesson 6. This enables deployment and can incur Azure charges. |
| [07: Custom action](07-custom-actions/) | Install the action metadata at `.github/actions/setup-python-env/action.yml` and update `run-tests.yml` together. |
| [08: Reusable workflows](08-reusable-workflows/) | Install `reusable-deploy.yml`, `azure-dev.yml`, and `manual-deploy.yml` under `.github/workflows`; keep the Azure configuration from lesson 6. |
| [09: Required checks](09-required-workflows/) | Install the final core `run-tests.yml`; keep the local action from stage 07. Configure the required check through repository settings. |
| [10: Artifacts](10-artifacts/) | Install `artifacts.yml` under `.github/workflows`. It is an independent manual lab, not another automatic CI pipeline. |
| [11: Runners](11-runners/) | Install `runner-matrix.yml` under `.github/workflows`. The default exercise uses hosted runners only. |
| [12: Environments](12-environments/) | Configure `pets-production` first, then install `protected-release.yml`. This workflow verifies an approved artifact without deploying. |
| [13: Copilot CLI](13-copilot-cli/) | Install `copilot-cli.yml`; retain `report.py` and both `runtime/package*.json` files at their solution paths. Keep the credential-free default; configure `pets-copilot` before a real CLI call. |
| [14: GitHub Agentic Workflows](14-agentic-workflows/) | Copy `pets-test-plan.md` to `.github/workflows`, compile with gh-aw v0.88.8, and review/commit its `.lock.yml` and action pins. Configure `pets-agentic` and Copilot authentication before any real run; outputs stay staged. |
| [15: Capstone](15-capstone/) | Install `capstone.yml`, the stage 07 local action, and the stage 08 reusable deployment workflow. Keep deployment off unless Azure/OIDC and `pets-production` are configured. |
| [16: Azure Pipelines migration](16-migration/) | Optional. Keep `azure-pipelines.yml` as an Azure DevOps source, never an Actions workflow. Install only `migrated-ci.yml` under `.github/workflows` for the manual GitHub parity lab. |

Security feature setup in lesson 2 is performed through GitHub settings and the
existing Dependabot configuration; there is no synthetic scanning workflow to copy.

The files are opt-in, but their triggers become active once installed. Read the
`on`, `permissions`, `environment`, and `if` blocks before pushing. Copying a
deployment workflow into an authenticated repository is not a harmless preview.

## Prerequisites and boundaries

- Core commands use Python 3.13, a supported Node 22 release, the server requirements,
  and the frontend lockfile. Do not replace them with the personal workshop's Node
  sample commands.
- `main` is the assumed default branch. If you use another name, update triggers,
  guards, rulesets, environment restrictions, and Azure federated subjects together.
- Configure environments before referring to them. A new YAML name can create an
  unprotected environment. Approval requires supported features and an eligible
  reviewer other than the person who initiated the run when self-review is disabled.
- Fork PR code has no deployment or AI credentials. Do not run it on a persistent
  self-hosted machine or through a privileged `pull_request_target` workflow.
- The artifact labs verify bytes from the same run. They do not establish producer
  identity or deploy an immutable image. Azure's `azd up` may rebuild the app.
- Preserve reviewed full-SHA action references and version comments when adapting
  the examples. Resolve an updated version's commit in the action's source
  repository; a movable major-version tag is not equivalent.

## Maintaining the examples

The local checker validates relative links, solution structure, and selected
teaching invariants. It is not a security scanner or a substitute for executing a
workflow. The standalone `actionlint` tool provides workflow/expression validation.
The checker explicitly distinguishes the migration's Azure Pipelines source and
the compiler-owned gh-aw lockfile from the hand-written Actions examples. Those
formats have their own policy tests; they are not silently excluded from validation.

From the repository root, with Python 3.13 available:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r content/github-actions/tools/requirements.txt
.venv/bin/python content/github-actions/tools/check_workshop.py
.venv/bin/python -m unittest discover -s content/github-actions/tools -v
```

On Windows, use the corresponding `.venv/Scripts/python.exe`. Install
[actionlint][actionlint] through its documented installation method, then validate
the workflow solution files, including the generated agentic lockfile (not
composite `action.yml` metadata or the Azure Pipelines source):

```bash
find content/github-actions/solutions -name '*.yml' \
  ! -name action.yml ! -name azure-pipelines.yml -print0 |
  xargs -0 actionlint
```

Run the existing application commands when changing runnable examples:

```bash
.venv/bin/python -m pip install -r app/server/requirements.txt
(cd app/server && DATABASE_PATH=:memory: PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m unittest test_app -v)
npm --prefix app/client ci
npm --prefix app/client run build
node --test app/client/start-test-server.test.js
(cd app/client && npx playwright install chromium)
(cd app/client && CI=true PYTHON="$PWD/../../.venv/bin/python" npm run test:e2e)
```

On Linux, macOS, or WSL, exercise lesson 13's offline boundaries without installing
Copilot, supplying an AI credential, or calling a model:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover \
  -s content/github-actions/solutions/13-copilot-cli -p 'test_*.py' -v
```

When updating lesson 13's CLI version, change `runtime/package.json`, regenerate
the lock with `npm install --package-lock-only --ignore-scripts --no-audit
--no-fund --omit-lockfile-registry-resolved` in that directory, and review every
changed dependency and integrity hash. Keep the helper's version check in sync.
The workflow must continue using `npm ci --ignore-scripts`; it must not regenerate
the lock on a runner. Validate a fresh install and the CLI's version/help without
providing AI credentials before authorizing any live run.

For lesson 14, install/select **gh-aw v0.88.8** as described in the lesson, then run:

```bash
.venv/bin/python content/github-actions/tools/check_agentic.py
```

This creates a temporary Git repository, copies the Markdown, generated lockfile,
and reviewed action-resolution cache to their installation paths, compiles in strict
mode, and checks for a byte-for-byte match. It never activates a workflow in this
repository, calls AI, or creates an issue. Compilation may need network access to
resolve dependencies. `--compiler /absolute/path/to/gh-aw` accepts a separately
installed pinned binary without replacing your personal CLI extension.

To refresh the stored snapshot after a source edit, use that same temporary layout:
copy `pets-test-plan.md` and `pets-test-plan.lock.yml` into `.github/workflows`,
and `actions-lock.json` into `.github/aw`. Run `gh aw compile pets-test-plan
--strict --no-check-update`, then copy the reviewed compiler outputs back into
`solutions/14-agentic-workflows/`. Never hand-edit the `.lock.yml`. Re-run the
checker and actionlint after refreshing it. A compiler or dependency upgrade is a
separate reviewed change, not a reason to ignore a freshness failure.

Locally valid YAML cannot verify GitHub-hosted OS behavior, reviewers, repository
settings, Azure trust, or Copilot policy/entitlement. Check those separately in an
owner-authorized practice repository. Never activate cloud or AI examples in the
source template just to test the docs.
The migration examples likewise don't prove Azure DevOps service connections,
hosted-agent capacity, branch policies, or cross-system parity until an owner
queues them against the same commit and reviews the evidence.

[workshop]: ../README.md
[actionlint]: https://github.com/rhysd/actionlint/blob/main/docs/install.md
