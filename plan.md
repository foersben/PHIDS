1. **Refactor `_extract_doc_metadata` in `scripts/governance/visualize_okf.py`**
   - Extract the frontmatter parsing into a new private helper `_parse_frontmatter`.
   - Extract the claims extraction into a new private helper `_extract_claims_from_fm`.
   - Update `_extract_doc_metadata` to use these helpers to flatten the logic and reduce the complexity score below 12.

2. **Verify Refactoring**
   - Read the modified file to confirm changes were correctly applied.

3. **Complete Pre-commit Steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

4. **Update `complexity.md` Memory Journal**
   - Append the required report block to `.agents/memory/complexity.md`.

5. **Submit PR**
   - Submit the refactoring pull request with the required details.
