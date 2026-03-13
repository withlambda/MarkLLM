# `.github/workflows/release.yml`

## Context
This GitHub Workflow automates the release process using the `release.sh` script. It allows triggering a new release directly from the GitHub Actions UI.

## Logic
1.  **Trigger**:
    *   `workflow_dispatch`: Manually triggered with an input parameter `version`.
2.  **Permissions**:
    *   Requires `contents: write` to push changes and tags.
3.  **Steps**:
    *   **Checkout**: Checks out the repository with full history (`fetch-depth: 0`) and authentication token.
    *   **Git Configuration**: Sets up a bot user (e.g., `github-actions[bot]`).
    *   **Run Script**: Executes `./release.sh` with the provided version.
4.  **Security and Integration**:
    *   Uses `GITHUB_TOKEN` for repository operations.
    *   **Note**: Tag pushes made with `GITHUB_TOKEN` do not trigger other workflows (like Docker publish) to prevent loops. For full automation, a Personal Access Token (PAT) with `repo` scope should be used instead.

## Inputs
*   `version`: The target version for the new release (e.g., `1.10.3`).
