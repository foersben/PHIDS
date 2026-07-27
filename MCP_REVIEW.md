# MCP Server Implementation Review

## Current State

The `phids/mcp_server.py` implementation exposes a Model Context Protocol (MCP) server that provides agents read-only access to the PHIDS plant-herbivore simulation engine configuration and telemetry outputs. It achieves this through declarative resources, inspection tools, and predefined prompts.

It provides:
- A `phids://config/draft.json` resource which returns a JSON dump of the active configuration `DraftState`.
- `runtime_snapshot()` tool which returns a performance-and-counts summary of the current draft state including: scenario metadata, grid dimensions, species counts, substance definition count, trigger rule counts, initial placement counts, and termination thresholds.
- `inspect_telemetry_schema(zarr_store_path: str)` tool to inspect `.zarr` telemetry files and metadata without fully loading them into memory.
- `validate_okf_compliance()` tool to run the OKF check script.
- `query_diagnostic_logs(limit: int = 80)` tool to get recent diagnostic logs emitted by the simulator.
- `analyze_simulation_drift()` prompt for guiding debugging agents through stochastic drift anomaly triage.

## What is up to date

The MCP server relies primarily on the `DraftState` singleton (`from phids.api.ui_state.state import get_draft`).
The serialization mechanism (`_draft_to_json` used by `active_draft_resource()`) delegates to `pydantic` and `dataclasses.asdict`. Thanks to this structure, it remains structurally sound and up-to-date even with new fields recently added to the `DraftState` such as `placement_mode`, `flora_placement_strategy`, `herbivore_placement_strategy`, and `active_batch_jobs` dynamically capturing the latest simulator layout without requiring manual maintenance of the export function. The integration uses the new modularized path `from phids.api.ui_state.state`.

## What is missing or could be improved

While the full config dump handles everything perfectly, the more targeted, manual tools can be improved:

1. **New `DraftState` features missing from `runtime_snapshot()`:**
    The `runtime_snapshot` tool explicitly lists the counts of various lists inside `DraftState` to avoid dumping the whole configuration. With recent additions like procedural placements, Mycorrhizal networks and batch jobs, the `runtime_snapshot` could be augmented to include summaries of these new modes.
    For instance:
    - Adding `placement_mode` (`"manual"` or `"procedural"`) to clarify what engine initialization logic will be run.
    - Adding `active_batch_jobs_count: len(draft.active_batch_jobs)`.
    - Exposing global configuration flags like `mycorrhizal_inter_species` which dramatically alter signal propagation behaviors.

2. **DSE (Design Space Exploration) & Batch Jobs Awareness Tools:**
    The simulator now has DSE and Batch capabilities natively. The MCP server could expose explicit tools or prompts to interact with DSE outcomes or batch run summaries. Providing a `query_batch_jobs()` tool would give the MCP agent real-time visibility into long-running tasks or evolutionary exploration results without directly scraping HTTP JSON artifacts manually.

3. **Missing Tool for Direct Batch Replay Evaluation:**
    While `inspect_telemetry_schema` checks an individual `.zarr` output store structure, adding a tool to digest the aggregated metrics inside `data/batches/{job_id}_summary.json` would streamline the agent workflows for ecological analytics.
