---
description: 'Generate comprehensive scholarly/scientific Google-style docstrings'
---

# TASK: Generate Scientific Docstrings

Act as a Scientific Documentation Agent. Add comprehensive Google-style docstrings to all provided Python files (including `__init__.py` packages, modules, classes, functions, methods, and test files).

### ⚠️ CRITICAL EXECUTION CONSTRAINTS
1. **DOCSTRINGS ONLY:** You are strictly forbidden from modifying, refactoring, or reformatting ANY actual source code, logic, variables, or imports. ONLY add or modify `"""` docstring blocks.
2. **NO TYPES IN DOCSTRINGS:** The codebase uses comprehensive Python type hints. Do NOT include type information in the `Args:`, `Returns:`, or `Yields:` sections. 
   - ❌ Bad: `param_name (int): Description`
   - ✅ Good: `param_name: Description`
3. **NO META-COMMENTARY:** Do not state the obvious or describe what you are doing. Never write phrases like "This module-level docstring provides a scholarly abstract..." Just write the abstract. 
4. **NO REDUNDANCY:** Do not repeat module-level claims inside functions if the information is already implied by the module description. Keep it DRY.

### 🧬 TONE & CONTENT
5. **SCHOLARLY TONE:** Maintain a rigorous, scientific, and academic tone. Detail the algorithmic mechanics and biological rationale (e.g., use terms like "metabolic attrition", "O(1) spatial hash lookups").
6. **COMPACTNESS:** Be concise while preserving scientific clarity. Use short sentences and bullet lists where appropriate. Avoid nested lists deeper than two levels.
7. **TEST FILES:** For test files, the module docstring must describe the experimental hypotheses. Inside each test function, document the expected invariant, the empirical rationale, and exactly *what* biological behavior is being verified and *why*.
8. **MODULE LEVEL:** Every file MUST start with a module-level docstring explaining its architectural role in the engine or API.

### 📐 FORMATTING & STRUCTURE
9. **SECTION INCLUSION:** Include Google-style sections ONLY when they contain meaningful content. Do not include empty section headers.
10. **SECTION ORDER:** When present, headers must appear in this EXACT order, matching this capitalization:
    `Args:`, `Attributes:`, `Returns:`, `Yields:`, `Raises:`, `Warnings:`, `Notes:`, `References:`, `See Also:`, `Examples:`, `Todo:`.
11. **MISSING INFO:** If a required scientific rationale or reference is unknown, do NOT invent one. Instead, include a concise `Notes:` entry indicating what data or citation is needed.
12. **TOOL COMPATIBILITY:** Use UTF-8 characters where necessary (e.g., Greek letters, ±), but ensure docstrings parse cleanly with Sphinx Napoleon. Use triple double-quotes (`"""`) for all docstrings.

---

### SUCCESS CRITERIA
- Every file starts with a module-level docstring.
- Every public class, function, and method has a Google-style docstring.
- Only non-empty headers are included, strictly adhering to the mandated order.
- Not a single line of actual source code is altered.

### EXAMPLE FORMAT TO STRICTLY FOLLOW

**Module/Class-Level:**
"""
Short architectural role or biological summary.

Attributes:
    attribute_name: Brief description of state/algorithmic role.

Notes:
    Brief scientific rationale or note on missing citation data.

References:
    - Author et al., Year, Journal, DOI.
"""

**Function/Method-Level:**
"""
One-sentence summary of purpose and scientific rationale.

Args:
    param1: Concise description and algorithmic role.
    param2: Concise description and biological interpretation.

Returns:
    result: Short description of returned object and its significance.

Raises:
    ValueError: Condition and why.

Notes:
    Data or citation required if applicable.

See Also:
    related_function
"""