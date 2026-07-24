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

### 1. Database Persistence Migration
Currently, the Bio-Database is persisted via a flat file (`src/phids/analytics/bio_database.json`). As the simulation complexity scales, especially when the DSE starts caching thousands of generated archetypes, we will migrate this.
- **Short Term:** Migrate flat-file JSON serialization to **SQLite** using SQLAlchemy.
- **Long Term:** Support for scalable graph/document databases (e.g., PostgreSQL JSONB) to allow for complex queries like "Find all herbivores immune to taxine".

### 2. DSE Configuration Sync
The current DSE configuration forms must be tightly linked to the new Bio-Database UI.
- The UI must dynamically populate the **Mode B: Constrained** archetypal dropdowns directly from the SQLite backend.
- The pre-flight invariant parser must read the Substance Trigger definitions and Diet matrices built in the visual editor to instantly block impossible survival parameters.
