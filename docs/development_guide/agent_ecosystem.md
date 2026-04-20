# Agent Ecosystem & MCP

To manage documentation, testing, and lifecycle operations reproducibly, PHIDS integrates an explicit human-and-agent governance model based on the Model Context Protocol (MCP).

## Agent Roles & Governance

To keep implementation truth, documentation truth, and verification truth separated until they can be deliberately reconciled, tasks are routed to specialized agents:

-   **`docs-librarian`**: The centralized coordinator for all documentation logic, structure, and validation. It maintains the Information Architecture (IA) and delegates concrete file writing.
-   **`docs-scientist`**: Dedicated to writing formal, equation-backed scientific and mathematical modeling documentation (like those found in the Scientific Model deep dives).
-   **`docs-operator`**: Focuses on operational, procedural guides tailored to developer execution, CI runbooks, and repository configurations.
-   **`git-ops`**: The sole agent authorized to manage repository commits, branches, and PR workflows. It safeguards clean commit slices and strictly respects remote-impacting authorizations.
-   **`test-ops`**: Triggers, evaluates, and resolves failures in the test suites, typing coverage, and benchmark outputs, isolating the smallest valid failing slice before pushing fixes upstream.

## Model Context Protocol (MCP) Capabilities

MCP defines the strict technical surface connecting the repository tooling to the AI agents. While the agent governance dictates *who* executes a task, the MCP capability layer defines exactly *what* an AI can read or execute through the connected PHIDS server.

It consists of three distinct classes:

-   **Resources**: Read-only contexts providing state visibility without execution side effects (e.g., test suite reports, architectural constraints, legacy provenance).
-   **Tools**: Executable actions governed by safety barriers. These actively modify the repository or the runtime environment.
-   **Prompts**: Standardized instructions utilized during specific triage operations to improve consistency.

Agents do not execute generic, arbitrary operations; rather, they rely on specifically registered MCP Tools assigned to their governance role to affect the repository deterministically.
