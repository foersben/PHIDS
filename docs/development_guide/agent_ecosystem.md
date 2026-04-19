# Agent Ecosystem & MCP

To manage documentation, testing, and lifecycle operations reproducibly, PHIDS integrates an explicit human-and-agent governance model based on the Model Context Protocol (MCP).

## Agent Roles & Governance

- **`docs-librarian`**: The centralized coordinator for all documentation logic, structure, and validation.
- **`docs-scientist`**: Dedicated to writing formal, equation-backed scientific and mathematical modeling documentation.
- **`docs-operator`**: Focuses on operational, procedural guides (such as this one) tailored to developer execution.
- **`git-ops`**: The sole agent authorized to manage repository commits, branches, and PR workflows.
- **`test-ops`**: Triggers, evaluates, and resolves failures in the test-suites and benchmark outputs.

## Model Context Protocol (MCP) Capabilities

MCP defines the strict technical surface connecting the repository tooling to the AI agents. It consists of:
- **Resources**: Read-only contexts (e.g., test suite reports, architectural constraints).
- **Tools**: Executable modifications governed by safety barriers.
- **Prompts**: Standardized instructions utilized during specific triage operations.

Agents do not execute generic operations; rather, they rely on specifically registered MCP Tools assigned to their governance role to affect the repository.
