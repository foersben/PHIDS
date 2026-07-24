---
type: workflow
description: Checklist for human-escalated tasks when agents are structurally blocked.
---

# Trigger

Run when blocked by lack of signing keys, repository secrets, interactive credential prompts, or manual confirmation gates.

# Standard Escalation Format

When handoff is needed, present a markdown checklist with:

1. **Context:** Exact tool/command that failed and why.
2. **Step-by-step Instructions:** Commands or actions the human operator must execute.
3. **Resumption:** How to signal completion or verify execution.

# Blocked Categories & Human Instructions

## 1. Commit Signing (GPG/SSH)

- **Problem:** Commit fails with `gpg: signing failed: No secret key` or SSH key locked.
- **Instruction:**
  1. Check keys: `gpg --list-secret-keys` or `ssh-add -l`.
  2. Unlock key: run a dummy signature like `echo "test" | gpg --clearsign` to prompt passphrase GUI, or `ssh-add ~/.ssh/id_ed25519`.
  3. Signal agent to retry commit.

## 2. GitHub Action Secrets

- **Problem:** Cannot set/rotate API tokens or tokens/secrets in GitHub UI.
- **Instruction:**
  1. Navigate to GitHub Repo -> Settings -> Secrets and variables -> Actions.
  2. Add/update secret name: `<SECRET_NAME>`.
  3. Signal agent that secret is set.

## 3. Interactive Credentials / MFA

- **Problem:** Terminal command prompts for interactive password/MFA token.
- **Instruction:**
  1. Run command directly in user terminal session.
  2. Log in / complete MFA.
  3. Resume agent execution.
