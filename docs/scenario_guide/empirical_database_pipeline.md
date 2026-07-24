---
type: roadmap
title: "The PHIDS Empirical Database Pipeline (ETL)"
status: planned
version: 1.0
description: "Implementation details for the biological ETL data pipeline to ingest, clean, normalize, and cluster traits into the empirical bio_database.json."
---

# Roadmap: The PHIDS Empirical Database Pipeline

This document defines the architecture, ingestion strategy, cleaning rules, and archetype extraction models required to compile biological trait databases into a compressed, engine-compatible `bio_database.json` payload.

---

## Phase 1: Source Ingestion

**Target Directory:** `src/data_pipeline/ingest/`

Write asynchronous fetching scripts to acquire datasets from the following primary endpoints:

1. **TRY Plant Trait Database:** Specific Leaf Area, Seed Dry Mass, Max Canopy Height, Lignin/Silica contents, Leaf Tensile Strength.
2. **Global Biotic Interactions (GLoBI):** "Eats" / "is eaten by" records for establishing default `DietCompatibilityMatrix` structures.
3. **Animal Diversity Web (ADW) / PanTHERIA:** Herbivore metabolic rates, daily consumption caps, weaning/litter counts, and split limits.
4. **Dr. Duke's Phytochemical and Ethnobotanical Databases (USDA):** Plant chemical compounds (Alkaloids, Tannins, Cyanogens) and active toxicology thresholds.
5. **The Pherobase:** Volatile Organic Compounds (VOCs) and semiochemical properties.

---

## Phase 2: Taxonomic Alignment & Imputation

**Target Directory:** `src/data_pipeline/cleaning/`

1. **Taxonomic ID Resolution:**
    * Query the **GBIF (Global Biodiversity Information Facility) API** to resolve taxonomical synonyms and map all species variants to unified Taxonomic IDs.
2. **KNN Imputation:**
    * Implement an imputation runner using `scikit-learn`'s `KNNImputer`.
    * Group entries by evolutionary family or genus to estimate missing attributes based on the nearest phylogenetic neighbors ($K=5$).

---

## Phase 3: Mathematical Normalization & Mapping

**Target File:** `src/data_pipeline/transform.py`

Map physical attributes to unitless float bounds in $[10^{-4}, 1.0]$ required by the ECS engine:

* **Photosynthetic Growth:** Map Specific Leaf Area (SLA) via Min-Max scaling to $growth\_rate$.
* **Max Energy Capacity:** Scale plant dry mass to a configured simulation ceiling (e.g. `100.0` units).
* **Morphological Defenses:**
  * Leaf tensile strength $\rightarrow$ `mechanical_damage_per_bite` ($0.0$ to $0.3$).
  * Lignin dry weight percentage $\rightarrow$ `digestibility_modifier` ($0.5$ to $1.0$).
* **Toxicity Rates:** Translate USDA $LD_{50}$ metrics into normalized `lethality_rate` constants.
* **Diffusion Speeds:** Map compound molecular weights to equivalent spatial diffusion coefficients.

---

## Phase 4: Archetype Extraction (Dimensionality Reduction)

**Target File:** `src/data_pipeline/archetype_extractor.py`

Prevent computational and UI bottlenecks by clustering species into distinct ecological strategies:

1. **K-Means Clustering:**
    * Execute K-Means clustering ($K=50$ for Flora, $K=50$ for Herbivores) over the normalized dataset.
2. **Centroid Representative Extraction:**
    * Identify the species situated closest to the center of each of the 50 clusters.
    * Map these Centroids as the official archetype names (e.g. using *Taxus baccata* as the representative for slow-growing toxic conifers).

---

## Phase 5: Synthesis & Trigger Logic Compiler

**Target File:** `src/data_pipeline/json_builder.py`

Compile flat clustered profiles into the deeply nested `bio_database.json` schemas:

1. **Cascade Synthesis Rules:**
    * If a species possesses both VOC signaling and chemical toxicity traits, generate a **Multi-Level Cascade Trigger** (`Condition: Herbivore -> Action: Signal. Condition: Signal -> Action: Toxin`).
2. **Resource Withdrawal Rules:**
    * For species with slow growth but high energy capacity (e.g. climax trees), auto-generate a **Resource Withdrawal Trigger** (senescence) that fires under sustained grazing pressure.
3. **Schema Serialization:**
    * Validate the generated JSON output against the active Pydantic schemas in `schemas.py` and output to `src/phids/analytics/bio_database.json`.

---

## Reference Script Specification (Data Engineer Agent instructions)

A dedicated data agent should implement these steps inside `src/data_pipeline/` using the following blueprint:

* `ingest.py`: Handles connection stubs and local storage of data dumps.
* `transform.py`: Implements taxonomic merging, KNN imputation, and Min-Max translation formulas.
* `archetype_extractor.py`: Configures scikit-learn K-Means and centroid extraction.
* `json_builder.py`: Validates and structures the final compiled JSON database.
