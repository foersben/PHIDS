---
type: rule
trigger: always_on
description: Commit signing and git security mandates
---

# Mandates

- **Signing Integrity:** Require GPG/SSH signature on all commits. Stop immediately if signing fails.
- **No Bypassing:** Ban bypassing signatures or editing configuration (e.g., `.git/config`, `user.name`, `commit.gpgsign`).
- **Escalation:** Ask human operator to unlock keys/resolve signing issues if a signed commit fails.
