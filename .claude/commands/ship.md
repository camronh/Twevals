Ship recent changes in the current branch to production.

Follow these steps in order:

## 1. Run Tests
- Execute `uv run pytest` to ensure all tests pass
- If tests fail, STOP and report the failures - do not proceed with shipping

## 2. Analyze Changes
- Run `git status` to see all changed files (committed and uncommitted)
- Run `git diff` to see uncommitted changes
- Run `git diff dev...HEAD` to see all changes since diverging from dev
- Understand what features/fixes/changes are being shipped


## 3. Update CHANGELOG.md
- Add a new version entry at the top (below "All notable changes...")
- Format: `{new_version} - {today's date in YYYY-MM-DD}`
- Analyze the git diff to auto-generate changelog entries
- Use these prefixes based on change type:
  - `Added:` for new features/functionality
  - `Changed:` for modifications to existing features
  - `Fixed:` for bug fixes
  - `Tests:` for test-related changes
- Write clear, concise descriptions (1-2 sentences per item)
- Group related changes together and changes on the same date should be grouped together. Look at the git history for that day to make sure everything is covered and not duplicated.
- Preserve existing changelog entries below


## 4. Update README.md (Only If Needed)
- Review if changes require README updates
- Update ONLY if new features need documentation or existing feature docs are outdated
- When updating:
  - Rewrite relevant sections to be current
  - Do NOT mention "this is an update" or "changed from old version"
  - Just make the content reflect current state
- Skip README updates for:
  - Internal refactoring
  - Bug fixes that don't change user-facing behavior
  - Minor changes

## 5. Commit Changes
- Stage and commit production ready changes:
  - If you worked on the current changes, then only commit what you worked on.
  - I tend to create notes and test scripts and notebooks. Try to avoid them but feel free to ask if you are unsure.
- IGNORE and do NOT commit:
  - Files you don't recognize as part of the project
  - Temporary files, IDE files, etc.
- Use commit message style:
  - Lowercase, imperative mood
  - Concise (2-5 words preferred)
  - Examples: "add export feature", "fix context bug", "update docs"
- Include all related changes in a single commit

## 7. Push and Merge Workflow

### If on a feature branch (not dev):
- Push current feature branch: `git push origin <feature-branch>`
- Checkout dev: `git checkout dev`
- Pull latest dev: `git pull origin dev`
- Merge feature branch into dev: `git merge <feature-branch>`
- Push dev: `git push origin dev`

### If already on dev:
- Push dev: `git push origin dev`

### Then merge dev to main:
- Checkout main: `git checkout main`
- Pull latest main: `git pull origin main`
- Merge dev into main: `git merge dev`
- Push main: `git push origin main`
- Return to dev: `git checkout dev`

## Error Handling
- If tests fail → stop and report
- If merge conflicts occur → stop and ask for help
- If unrecognized files exist → ignore them, proceed with known files
- If no changes to commit → report and exit gracefully

## Summary Output
After successful ship, provide:
- Version number shipped
- Brief summary of changes
- Branches involved (feature branch if applicable, dev, main)
