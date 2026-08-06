## The Discrepancy

In the PHIDS engine, the mathematical behavior of plant morphological defenses and dynamic resource reallocation is documented as the ultimate source of truth in `docs/scientific_model/morphological_defenses.md`.

The documentation explicitly defines the schema configuration for `ResourceWithdrawalAction` (the action configuring rate-limited phloem nutrient translocation):
```python
class ResourceWithdrawalAction(StrictBaseModel):
    """Action configuring rate-limited phloem nutrient translocation."""
    type: Literal["resource_withdrawal"] = "resource_withdrawal"
    apparent_nutrition_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    withdrawal_duration: int = Field(default=5, ge=1)
```

However, prior to this fix, the actual codebase in `src/phids/api/schemas/triggers.py` incorrectly defined these default values:
* `apparent_nutrition_factor` had a default of `1.0` (which effectively disabled the defense mechanic entirely, since 1.0 means no apparent nutrition drop).
* `withdrawal_duration` had a default of `10` (which was double the documented baseline).

This discrepancy represents a direct violation of the scientific contract: newly created UI rules or API payloads that omitted these fields were inadvertently creating non-functional defense mechanisms that did not reduce the flow-field attractiveness as intended.

## The Action

I modified `src/phids/api/schemas/triggers.py` directly:
- Altered the `default` for `apparent_nutrition_factor` in `ResourceWithdrawalAction` from `1.0` to `0.1`.
- Altered the `default` for `withdrawal_duration` in `ResourceWithdrawalAction` from `10` to `5`.

## The Justification

This change was strictly necessary for the scientific and architectural integrity of the simulation.
1. **Mathematical Reproducibility:** By returning the defaults to the documented values, newly created configuration payloads will now accurately engage the rate-limited phloem translocation mechanics. An apparent nutrition factor of `0.1` successfully flattens the local attractant gradient ($F(x,y)$), steering herbivore swarms away from the defended plant as designed.
2. **Strict Documentation Alignment:** As Canon, the documentation acts as the absolute law. The parameters explicitly mapped out in the appendix of the markdown files must be identical to the Pydantic schemas they describe.
3. **Engine Safety:** Adjusting Pydantic defaults poses zero risk of crashes. I verified the change by running the complete pytest suite and executing ruff lint/format passes, all of which completed successfully. No mathematical determinism tests failed because integration tests actively supply explicit payloads rather than relying exclusively on default triggers.
