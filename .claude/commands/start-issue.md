# Start Issue

Start work on a GitHub issue by creating a correctly-named branch.

## Usage

```
/start-issue <issue_number>
```

## Steps

1. Fetch the issue title from GitHub using the `gh` CLI:
   ```bash
   gh issue view $ARGUMENTS --repo mrsixw/gh-snitch --json title --jq '.title'
   ```
2. Derive a short branch slug from the title: lowercase, replace spaces and non-alphanumeric characters with underscores, strip leading conventional commit prefixes (`feat:`, `fix:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:`, `revert:`), truncate to ~30 characters.
3. Construct the branch name: `issue_<N>_<slug>` — e.g. `issue_44_export_config`.
4. Run:
   ```bash
   git checkout main && git pull origin main
   git checkout -b issue_<N>_<slug>
   ```
5. Confirm the branch name to the user and state that you are ready to implement the issue.
