# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Executable entrypoint for running the PHIDS MCP server directly."""

from phids.mcp.app import run_mcp_server

if __name__ == "__main__":
    run_mcp_server()
