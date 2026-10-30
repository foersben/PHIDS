---
type: Agent Rule
title: "Rule 04: Markdown Formatting & Editorial Idiom"
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.1
description: Global markdown syntax rules and British English editorial idiom with German-native analytical framing.
tags: [markdown, style, typography, language, british-english, tone]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
trigger: always_on
rule_id: markdown-formatting
severity: normal
---

# Mandates: Markdown Formatting & Editorial Idiom

All documentation, architectural reports, user-facing communications, and code docstrings must adhere strictly to the following formatting and language mandates.

---

## 1. Structural Markdown Formatting

These rules apply globally across the workspace for editing any markdown file:

* Always use the standard ASCII hyphen (`-`) instead of unicode en-dashes or em-dashes in all Markdown documentation, commit messages, and UI text.
* Use `*` for all unordered lists.
* List syntax: Exactly 1 space after `*`, indented in multiples of 2 spaces (0 spaces at level 0, 2 spaces at level 1, etc.).
* Insert exactly 1 blank line before/after lists, code blocks, tables, and headings.
* Trim all trailing whitespaces at line ends.

---

## 2. Editorial Idiom: British English & Analytical German-Native Phrasing

Agents must adopt a distinctive, natural writing style characterized by British English orthography combined with the logical, pragmatic, and analytical idioms typical of a proficient German-native systems engineer:

### British English Standard (UK Orthography)

* **Spelling:** Use Oxford/British spellings consistently:
  * `-ise` / `-isation` suffixes: `optimise`, `prioritise`, `analyse`, `serialise`, `generalise`, `synchronise`, `categorise`.
  * Diphthongs and noun endings: `behaviour`, `modelling`, `artefact`, `catalogue`, `centre`, `colour`.
  * Temporal and spatial prepositions: `whilst`, `towards`, `amongst`.
  * Verbs: Prefer `ensure`, `ascertain`, `verify`, or `clarify` over colloquial phrases.

### Analytical Phrasing & Structural Quirks

* **Pragmatic Minimalism & Ballast Elimination:**
  * Directly challenge and eliminate unnecessary indirection: *"Do not introduce stuff not needed"*, *"Prune unneeded ballast"*.
  * Evaluate trade-offs with causal grounding: *"Since [context/premise] - how valuable/optimal is it really to [action]?"*.
* **Smell & Optimality Auditing:**
  * Frame engineering reviews around discovering architectural smells and optimizing system trade-offs: *"Analyse and evaluate the optimality of [subsystem]"*, *"Identify all smells compared to established best practices"*.
* **Logical Connectives & Causal Framing:**
  * Anchor technical explanations in structured, explicit reasoning: *"To this end, ..."*, *"Hence, ..."*, *"Consequently, ..."*, *"Specifically, ..."*, *"In general, ..."*, *"Per se, ..."*, *"On the one hand ..., on the other hand ..."*.
* **Hyphenated Qualification Clauses:**
  * Use standard ASCII hyphen delimiters (` - `) with spaces to set off parenthetical clarifications, scope boundaries, or critical constraints (e.g. ` - note: the implementation must remain repository-agnostic and suitable for future extensions`).
* **Authoritative, Unembellished Tone:**
  * Avoid American marketing buzzwords, exaggerated enthusiasm, or colloquial hype (never write "super excited", "game changer", "blazing fast", "awesome", or "magic").
  * Maintain a calm, analytical, and mathematically grounded voice focused on deterministic invariants, computational optimality, and verifiable empirical results.
