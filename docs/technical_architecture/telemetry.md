# Telemetry & Export

The value of the PHIDS simulator rests on its capacity to log, analyze, and export ecological dynamics reproducibly. The system treats telemetry capture not as an afterthought, but as a primary output constraint synchronized strictly to the conclusion of the simulation tick.

## The Tick Metrics Layer

After the completion of the `signaling` phase, the engine consolidates critical system markers—total flora energy, species extinction events, and precise tallies of immediate death causes (e.g., reproduction exhaustion versus herbivore predation)—into a discrete `TickMetrics` payload.

## Polars Data Aggregation

To manage substantial longitudinal data streams gracefully, the `TelemetryRecorder` relies on the `polars` library. Instead of actively concatenating DataFrames per tick, the recorder appends to Python dictionaries. Upon request (for example, during CSV export), it executes a lazy materialization into a typed Polars DataFrame. This flattened scalar table expands seamlessly as new species or phenomena occur.

## Replay Buffers and Snapshot Generation

Simultaneous to metric tracking, PHIDS serializes the current continuous-field representations via `msgpack`. The `ReplayBuffer` writes these byte-streams to a length-prefixed log file on disk. These binary records permit exact state reconstruction without the overhead of complete ECS snapshots, providing the basis for deterministic, post-hoc analysis.

## Termination Protocol ($Z_1$ - $Z_7$)

The engine integrates continuous checks against operational bounds:
- **Max Duration ($Z_1$)**: Cap on ticks.
- **Extinctions ($Z_2, Z_3, Z_4, Z_5$)**: Target or global population collapse.
- **Runaway Growth ($Z_6, Z_7$)**: Exceeding specified energy/population carrying capacities.

Termination flags generated here provide vital context as to *why* a particular experimental model collapsed, allowing for deeper scientific comparison across scenario families.
