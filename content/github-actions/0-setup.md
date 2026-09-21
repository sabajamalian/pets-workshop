# Workshop Setup

| [← GitHub Actions: From CI to CD][walkthrough-previous] | [Next: Introduction & Your First Workflow →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

To complete this workshop you will need to create a repository with a copy of the contents of this repository. While this can be done by [forking a repository][fork-repo], the goal of a fork is to eventually merge code back into the original (or upstream) source. In our case we want a separate copy as we don't intend to merge our changes. This is accomplished through the use of a [template repository][template-repo]. Template repositories are a great way to provide starters for your organization, ensuring consistency across projects.

The repository for this workshop is configured as a template, so we can use it to create your repository.

## Scenario

The shelter's volunteers need a safe place to learn CI/CD without changing the live adoption service. Use your own training repository and review each workflow before enabling it.

## Background and prerequisites

- **Learners** need a GitHub account, permission to push to their training repository, Actions enabled, and a codespace or local editor with Git, Python 3.13, and a current Node.js 22 release (at least 22.12). The Python compatibility exercise also tests 3.12 and 3.14.
- **Repository owners** configure security features, Actions policies, and branch rulesets. Public repositories support the core exercises on GitHub Free; private repository security and protection features depend on the account's plan and enabled products.
- **Organization owners** handle organization-wide required workflows. This is a separate, plan-dependent extension of the repository status-check exercise, not a learner prerequisite.
- **Azure deployment is optional.** It requires an approved subscription, permission to create resources and a federated identity, and permission to configure repository variables. Resources incur charges until removed. You can read lessons 6 and 8 without deploying and still complete the CI exercises.
- Advanced environment protections, runner administration, and live AI use have their own owner and plan requirements. The default AI exercises don't need credentials or a paid model.

No checked-in solution runs automatically. GitHub only discovers workflow files installed directly into `.github/workflows/`. The [solution guide][solutions] lists each stage's exact copy destinations and companion files. Copy one lesson's named files, not the whole solution tree. A `run-tests.yml` snapshot replaces that file from the previous lesson; it isn't a second workflow.

> [!IMPORTANT]
> Repository creation, pushes, security settings, Azure provisioning, and runner registration are exercises you choose to perform in your own training account. Don't use production credentials, register a persistent runner for untrusted PRs, or enable deployment snapshots before reviewing their prerequisites.

## Create your repository

Let's create the repository you'll use for your workshop.

1. Navigate to [the repository root][repo-root]
2. Select **Use this template** > **Create a new repository**

    ![Screenshot of Use this template dropdown](../shared-images/setup-use-template.png)

3. Under **Owner**, select the name of your GitHub handle, or the owner specified by your workshop leader.
4. Under **Repository**, set the name to **pets-workshop**, or the name specified by your workshop leader.
5. Ensure **Public** is selected for the visibility, or the value indicated by your workshop leader.
6. Select **Create repository from template**.

    ![Screenshot of configured template creation dialog](../shared-images/setup-configure-repo.png)

In a few moments a new repository will be created from the template for this workshop!

## Open your codespace

Now let's open a codespace so you have a development environment ready to go.

1. Navigate to the main page of your newly created repository.
2. Select **Code** > **Codespaces** > **Create codespace on main**.

    In a few moments a codespace will open in your browser with a full VS Code editor. This is where you'll create and edit files throughout the workshop.

> [!TIP]
> If your codespace ever disconnects or you close the tab, you can reopen it by navigating to your repository and selecting **Code** > **Codespaces** and the name of your codespace.

## Summary and next steps

You've created the repository and opened a codespace. Next let's [create your first workflow][walkthrough-next].

## Resources

- [GitHub Actions usage and billing][actions-billing]
- [GitHub security feature availability][security-availability]
- [Installing Node.js][node-download]
- [Opt-in solution guide][solutions]

| [← GitHub Actions: From CI to CD][walkthrough-previous] | [Next: Introduction & Your First Workflow →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[fork-repo]: https://docs.github.com/get-started/quickstart/fork-a-repo
[template-repo]: https://docs.github.com/repositories/creating-and-managing-repositories/creating-a-template-repository
[repo-root]: /
[actions-billing]: https://docs.github.com/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions
[security-availability]: https://docs.github.com/get-started/learning-about-github/about-github-advanced-security
[node-download]: https://nodejs.org/en/download
[solutions]: solutions/README.md
[walkthrough-previous]: README.md
[walkthrough-next]: 1-introduction.md
