# Telemetry & Export

The true value of the PHIDS simulator rests on its capacity to log, analyze, and export ecological dynamics reproducibly. The system treats telemetry capture not as an afterthought, but as a primary mathematical constraint synchronized strictly to the conclusion of the simulation tick.

## The Tick Metrics Layer

After the completion of the `signaling` phase, the engine consolidates critical system markers into a discrete `TickMetrics` payload. This includes total flora energy, species extinction events, and precise tallies of immediate biological death causes:
- Reproduction exhaustion
- Mycorrhizal link construction cost
- Herbivore predation
- Toxin synthesis maintenance (Defense Economy)
- Natural metabolic deficit

## Polars Data Aggregation

To manage substantial longitudinal data streams gracefully without memory leaks, the `TelemetryRecorder` relies on the high-performance `polars` library.

Instead of actively concatenating multi-dimensional DataFrames per tick (which induces massive O(N^2) overhead on array resizing), the recorder appends raw Python dictionaries to a list. Upon request (for example, during a CSV export or UI polling event), it executes a lazy materialization into a statically typed Polars DataFrame. This flattened scalar table expands seamlessly as new species emerge or go extinct without requiring full grid scans.

## Replay Buffers and Snapshot Generation

Simultaneous to metric tracking, PHIDS serializes the current continuous-field representations via `msgpack`. The `ReplayBuffer` writes these zlib-compressed byte-streams to an append-only, length-prefixed binary log file on disk.

These binary records permit exact state reconstruction without the overhead of complete ECS snapshots, providing the basis for deterministic, post-hoc analysis. You can seamlessly rewind the simulation without recalculating diffusion matrices.

## Termination Protocol ($Z_1$ - $Z_7$)

The engine integrates continuous mathematical checks against operational boundaries. If any of these bounds are crossed, the loop immediately halts execution and logs the termination code into the telemetry output:

- **Max Duration ($Z_1$)**: A predetermined cap on simulation ticks. The scenario successfully ran its course without collapsing.
- **Extinctions ($Z_2, Z_3, Z_4, Z_5$)**: Target or global population collapse. A species was entirely wiped out by starvation, out-competition, or predation.
- **Runaway Growth ($Z_6, Z_7$)**: Exceeding specified energy/population carrying capacities. The biological parameters were unbalanced, causing a trophic explosion that would otherwise freeze the CPU.

Termination flags generated here provide vital context as to *why* a particular experimental model collapsed, allowing for deeper scientific comparison across scenario families and parameter sweeps.
