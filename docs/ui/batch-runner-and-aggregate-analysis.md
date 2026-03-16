# Batch Runner and Aggregate Analysis

The PHIDS batch runner provides deterministic, reproducible Monte Carlo analysis for scenario-level robustness assessment under stochastic movement and interaction pathways. In this surface, a single validated draft scenario is executed across multiple independent seeds through a process-isolated execution model, and the resulting trajectories are aggregated into statistical summaries that preserve the temporal structure of population dynamics.

The implementation separates batch computation from live single-run rendering in order to preserve operational clarity. Runtime batch workers are launched via `ProcessPoolExecutor` and emit run-level telemetry that is consolidated into aligned aggregate arrays (mean, standard deviation, extinction/survival metrics) and persisted to `data/batches/*_summary.json`. The UI layer then reconstructs chart and table representations from this persisted aggregate state, allowing the operator to revisit completed analyses without re-running the simulation.

Before persistence, aggregate payloads are recursively sanitized to strict JSON-safe values. Any
non-finite float (`NaN`, `+inf`, `-inf`) is normalized to `null`, and summary files are written
with `allow_nan=False`. This guarantees standards-compliant JSON documents and prevents frontend
`JSON.parse` failures when loading persisted batch artifacts.

This architecture couples deterministic simulation mechanics with publication-oriented observability. The computational branch computes aggregate trajectories and probabilistic endpoints, while the UI branch provides interactive chart controls, tabular decimation, and export pathways that maintain consistency with selected display state. Consequently, the same aggregate object can be inspected qualitatively in browser charts and exported quantitatively as CSV/LaTeX/TikZ artifacts for manuscript-grade reporting.

## Execution and persistence workflow

1. Configure runs and max ticks in `UI -> Batch Runner`.
2. Submit a job (`POST /api/batch/start`).
3. Poll ledger/detail views (`/api/batch/ledger`, `/api/batch/view/{job_id}`).
4. Persisted summaries are written automatically to `data/batches/{job_id}_summary.json`.
5. Reload previously computed summaries into the active ledger via `POST /api/batch/load-persisted`.

## Batch detail customization surface

Completed jobs expose two analysis tabs:

- `Charts`: mean±sigma population trajectories and survival curve visualization.
- `Data Grid`: decimated aggregate table preview with column selection controls.

Both tabs follow an explicit submission model so the analyst can stage multiple parameter edits before committing them:

- `Apply Chart Settings` commits preset/title/axis selections to the rendered figure and export links.
- `Apply Table Settings` commits decimation/column projection changes to the table preview and table-oriented exports.

This avoids accidental high-frequency redraws during exploratory editing and keeps exported artifacts aligned with deliberate UI confirmation.

The following controls are available in the detail fragment:

- `Preset` chart configurations for common interpretation modes (`Balanced overview`, `Collapse risk focus`, `Predator pressure focus`, `Survival probability only`).
- `Chart title`, `X-axis label`, `Population axis label` (chart metadata tuning).
- `Export tick interval` (row decimation stride for table-oriented exports).
- `Columns` (CSV/LaTeX table projection of aggregate fields).

## Export semantics

Batch export endpoint: `GET /api/batch/export/{job_id}`

Supported query parameters:

- `format=csv|tex_table|tex_tikz`
- `chart_type=timeseries|survival` (TikZ mode)
- `tick_interval>=1`
- `columns=...` (CSV and LaTeX table export projection)
- `title`, `x_label`, `y_label` (TikZ export metadata)

The decimation and projection settings are applied before serialization so the generated artifact remains aligned with the active data-grid interpretation. Float rendering in table exports is constrained to fixed precision (`%.2f`) to maintain manuscript-safe table widths.

Telemetry retention remains bounded at recorder level (`MAX_TELEMETRY_TICKS`) and UI table previews use bounded windows to avoid backend/browser overload during long-running sessions.

## Statistical interpretation guidance

The aggregate chart composes:

- mean population trajectories for flora and predators,
- standard-deviation envelopes around each mean,
- per-tick survival probability as a horizon-level persistence metric.

The survival curve should be interpreted as the fraction of runs retaining non-zero flora population at each aligned tick. This quantity complements extinction probability by preserving time-localized collapse behavior rather than collapsing all events into a single terminal scalar.
