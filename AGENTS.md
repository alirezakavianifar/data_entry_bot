
# Agent Instructions

## Git Remote

Changes must be pushed to: **[github.com/alirezakavianifar/data_entry_bot.git](https://github.com/alirezakavianifar/data_entry_bot.git)**

Ensure the remote `origin` points to this URL. If not configured, use: `git remote add origin https://github.com/alirezakavianifar/data_entry_bot.git` or `git remote set-url origin <url>` to update).

## .gitignore

If `.gitignore` does not exist, create one based on the codebase structure and language. Adapt entries to match the project's technologies and build output locations.

## Git Push & Deploy Workflow

When performing git operations, follow these specific guidelines based on the user's prompt:

1. **Stage all changes**: standard `git add .`
2. **Infer Commit Message**: Generate a concise, descriptive, and professional commit message based on the recent file changes and conversation context. Do not ask the user for a commit message unless they explicitly provide one.
3. **Commit**: `git commit -m "<inferred_message>"`
4. **Push**: `git push` (or `git push -u origin <branch>` if the upstream is not set).

### Execution Rules by Keyword

- **If the keyword `push` is used alone** (e.g., "push", "please push these changes"):

  - ONLY execute steps 1-4 to stage, commit, and push to GitHub.
  - DO NOT execute any post-push build or deployment scripts.
- **If the keyword `push&deploy` (or `push & deploy` / `push and deploy`) is used**:

  - Execute steps 1-4 to push changes to GitHub.
  - AND launch post-push deployment/build scripts in visible interactive PowerShell terminal windows on the user's desktop using `Start-Process powershell.exe` as necessary based on modified files:
    - If changes correspond to backend: `Start-Process powershell.exe -ArgumentList "-NoExit -ExecutionPolicy Bypass -File E:\projects\leitner-learning-platform\scripts\deploy-to-server.ps1"`
    - If changes correspond to frontend: `Start-Process powershell.exe -ArgumentList "-NoExit -ExecutionPolicy Bypass -File E:\projects\leitner-learning-platform\scripts\build-apk.ps1"`
    - If changes correspond to both, execute both `Start-Process powershell.exe` commands.
  - After running `scripts/build-apk.ps1`, ensure `app-premium-release.zip` contains the new `app-premium-release.apk` and upload to the Rubika bot via `scripts/upload-to-rubika.py`.

**Note:** You should proactively execute these commands without asking for extra confirmation.

## Language Rule

- Always respond and answer in English. Even if the user asks questions or provides input in another language (such as Persian), the agent must write all explanations, responses, and comments in English.

## README Requirement

- Always ensure the remote repository has an up-to-date `README.md` file that explains everything about the project, from how it is set up to how it is run. Include every single detail necessary so that if we were to run the project in the future, we can easily follow the steps in the README file and do exactly that.
