---
type: scenario_guide
title: "Database & UI Roadmap"
status: active
version: 0.1
description: "Roadmap for Database and UI in PHIDS."
---

# Bio-Database & UI Architecture Roadmap

The Bio-Database serves as the definitive catalog of biological archetypes-the raw genetic material available to the simulation engine and the Design Space Exploration (DSE) optimizer.

## Current Achieved State (v0.6)

We have successfully decoupled and modernized the visual editor and underlying schema to prepare for full-scale DSE integration and future database persistence.

### 1. Structural Decoupling of Archetypes
- **Standalone Substances:** Substances are no longer hardcoded as localized parameters inside Flora trigger rules. They exist as independent, top-level entities in the database. This allows both the user and the DSE optimizer to freely mix and match toxins, repellents, and signals across different flora species.
- **Herbivore Diet Matrices:** Herbivore dietary restrictions are now configured via graphical checkboxes drawn dynamically from the registered Flora catalog, producing explicit, machine-readable intersection arrays.
- **Visual Trigger Rules Builder:** The manual JSON editor has been entirely replaced with a graphical rule builder. It enforces structural logic (such as implicit `ALL_OF` arrays for activation conditions) preventing syntax errors before they hit the simulation engine.

### 2. Headless UI Validation
- We instituted a purely headless, blazing-fast validation suite (`test_ui_static.py`) utilizing `FastAPI TestClient`, `BeautifulSoup4`, and Node.js (`node -c`).
- This intercepts all DOM structure modifications and aggressively parses any injected HTMX/Javascript logic for `SyntaxError`s, protecting the complex interactive views.

---

## Future Goals & Next Steps

### 1. Database Persistence (Implemented: DuckDB)

The Bio-Database is persisted in a single-file columnar DuckDB database
(`src/phids/analytics/bio_database.duckdb`). This supersedes the previous
flat-file JSON approach and the SQLite short-term plan from v0.6.

**Why DuckDB over SQLite:**
- Columnar storage enables partial loading: read only `growth_rate` for
  all flora without deserializing trigger rules.
- Native STRUCT/LIST types store trigger rule condition trees as proper typed
  columns, not opaque JSON strings.
- Native Polars round-trip (`duckdb.table('flora').pl()`) - zero conversion overhead.
- Direct Parquet federation: the pipeline's ingest caches are queryable
  via `SELECT * FROM 'cache/pantheria_raw.parquet'` without loading.
- Full SQL interface for future HTMX API endpoints with filtering and paging.
- Scales to the DSE genotype cache (5-50 MB at 10,000 evaluations).

**File layout:**
- `bio_database.duckdb` - primary source of truth (queryable)
- `bio_database.json` - generated export for engine compatibility (derived artifact)
- `manifest.json` - provenance export from the DuckDB provenance table

**Long-Term:** As DSE genotype caching grows into hundreds of thousands of
entries, the same DuckDB file absorbs the load without schema changes.
A read replica or PostgreSQL migration is supported via DuckDB ATTACH.

### 2. DSE Configuration Sync

The current DSE configuration forms must be tightly linked to the Bio-Database.
- The UI must dynamically populate the **Mode B: Constrained** archetypal
  dropdowns by querying `SELECT canonical_name, growth_rate FROM flora_species`.
- The pre-flight invariant parser reads Substance Trigger definitions and
  Diet matrices from DuckDB to block impossible survival parameters instantly.
- `BioQuery.toxic_flora(conn, min_lethality=5.0)` provides the substance
  compatibility filter for the DSE optimizer.
