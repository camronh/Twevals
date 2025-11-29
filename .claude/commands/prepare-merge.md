Prepare documentation updates before merging a feature branch.

**Arguments:** Specify the target branch to compare against (default: `dev`)

Follow these steps:

## 1. Analyze Branch Changes
- Run `git log <target>..HEAD --oneline` to see commits
- Run `git diff <target>..HEAD --stat` to see changed files
- Read key changed files to understand what was implemented
- Summarize the features/changes in the branch

## 2. Update CHANGELOG.md
- Add entries to the "Unreleased" section
- Use these prefixes:
  - `Added:` for new features
  - `Changed:` for modifications
  - `Fixed:` for bug fixes
  - `Tests:` for test changes
- Write concise descriptions (1-2 sentences)
- Don't duplicate existing entries

## 3. Update Documentation (If Needed)
Review if changes require updates to:
- `docs/` directory (Mintlify docs)
- `README.md`

**Update docs when:**
- New user-facing features were added
- Existing feature behavior changed
- New CLI flags or API endpoints were added

**Skip docs for:**
- Internal refactoring
- Bug fixes without behavior changes
- Test-only changes

When updating, write docs as if they're the current state - don't mention "updated" or "changed from".

## 4. Summary
Report:
- What features/changes were found
- What documentation was updated
- What was skipped and why
