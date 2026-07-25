---
type: scientific_model
title: Morphological Defenses and Dynamic Resource Reallocation
status: active
version: 1.1
description: Mathematical and biological formulation of constitutive morphological defenses, digestibility modulation, and rate-limited phloem translocation in PHIDS.
tags:
- phids
- ecs
- defenses
- phloem
- mathematical-biology
timestamp: "2026-07-25T18:40:00Z"
resources:
- src/phids/api/schemas/species.py
- src/phids/api/schemas/triggers.py
- src/phids/engine/components/plant.py
- src/phids/engine/systems/lifecycle.py
- src/phids/engine/systems/interaction/feeding.py
- src/phids/engine/core/flow_field.py
---

This document provides the formal mathematical and biological formulation for plant morphological (constitutive) defenses and dynamic resource reallocation (apparent nutrition withdrawal) in the PHIDS ecosystem simulation model.

---

## 1. Biological and Ecological Context

Plants possess two distinct evolutionary defense paradigms against herbivory:

1. **Constitutive (Morphological) Defenses**: Permanent structural barriers such as trichomes, thorns, spines, and indigestible cell-wall compounds (lignin and silica). These defenses are metabolically fixed and directly impair herbivore feeding mechanics or reduce nutrient assimilation efficiency during every trophic attack.
2. **Inducible Defenses & Dynamic Allocation**: Physiological responses catalyzed by herbivore damage or volatile organic compound (VOC) warning signals. Upon perception, plants actively withdraw mobile nutrients and carbohydrates from vulnerable tissues (leaves and shoots) via vascular phloem transport into below-ground root sinks, temporarily lowering their nutritional attractiveness to foraging herbivores.

---

## 2. Mathematical Formulation

### 2.1 Constitutive Mechanical Attrition

Mechanical defenses (thorns and spines) inflict physical damage on grazing mouthparts during feeding events. Let $m_{\text{bite}} \ge 0$ represent the species-specific mechanical damage coefficient per bite, and $\rho_{\text{morph}} \in [0, 1]$ represent the herbivore's morphological resistance. The integer headcount reduction $\Delta n$ for a swarm cohort of size $n(t)$ feeding on plant tissue is given by:

$$\Delta n = \left\lfloor m_{\text{bite}} \cdot (1 - \rho_{\text{morph}}) \right\rfloor$$

$$n(t + \Delta t) = \max\left(0, n(t) - \Delta n\right)$$

Where $\lfloor \cdot \rfloor$ denotes the floor function, enforcing discrete integer mortality within the herbivore population cohort.

---

### 2.2 Caloric Attenuation & Digestibility Discounting

Structural cell-wall barriers (lignin and silica) reduce the fraction of ingested plant biomass that herbivores can digest and metabolize into reproductive energy reserves. Let $\mu_{\text{digest}} \in [0, 1]$ represent the plant's digestibility modifier and $\delta_{\text{eff}} \ge 0$ represent the herbivore's digestive adaptation efficiency.

Given total plant energy consumed $E_{\text{consumed}}$, the net metabolized energy $E_{\text{metabolized}}$ added to the herbivore energy pool is:

$$\eta_{\text{net}} = \min\left(1.0, \max\left(0.0, \mu_{\text{digest}} \cdot \delta_{\text{eff}}\right)\right)$$

$$E_{\text{metabolized}} = E_{\text{consumed}} \cdot \eta_{\text{net}}$$

---

### 2.3 Rate-Limited Phloem Translocation Kinetics

When a plant activates a `resource_withdrawal` defense action, it commits to reducing its apparent nutritional factor $N(t)$ toward a target factor $N_{\text{target}} \in [0, 1]$ (where lower values represent lower nutritional attraction).

Because carbohydrate transport through vascular phloem sieve tubes is limited by hydrostatic pressure gradients and fluid viscosity, the transition is governed by a first-order rate-limited differential equation with translocation rate $k_{\text{trans}} \in (0, 1]$:

$$\frac{d N(t)}{dt} = -k_{\text{trans}} \cdot \left(N(t) - N_{\text{target}}\right)$$

In discrete simulation time with tick step $\Delta t = 1$:

**Active Withdrawal Phase** ($\tau_{\text{withdrawal}} > 0$):

$$N^{t+1} = N^t - k_{\text{trans}} \cdot \left(N^t - N_{\text{target}}\right)$$

**Recovery Phase** ($\tau_{\text{withdrawal}} = 0$):

$$N^{t+1} = N^t + k_{\text{trans}} \cdot \left(1.0 - N^t\right)$$

!!! note "Scientific Progression: Instantaneous Scalar Toggle vs. Phloem Translocation"
    Earlier engine iterations toggled `apparent_nutrition_factor` instantaneously on tick 0. Real-world botany requires active vascular phloem transport to translocate mobile carbohydrates from leaves to roots. PHIDS models rate-limited phloem translocation ($\Delta N = -k_{\text{trans}} (N^t - N_{\text{target}})$), recreating the empirical biological vulnerability window where grazing herbivores can continue feeding during the initial translocation phase before peak suppression is reached.

---

### 2.4 Attractant Field Gradient Scaling

The spatial attractiveness of a plant cell $(x, y)$ to foraging herbivores in the Numba-accelerated flow-field solver is scaled directly by the plant's current apparent nutrition factor $N(x, y)$:

$$F(x, y) = \alpha \cdot \left(E_{\text{plant}}(x, y) \cdot N(x, y)\right) - \beta \cdot \sum_{k} T_k(x, y)$$

Where $E_{\text{plant}}(x, y)$ is the total plant energy, $T_k(x, y)$ represents localized repellent toxin concentrations, and $\alpha, \beta$ are flow-field weighting coefficients. Down-regulating $N(x, y)$ flattens the local attractant gradient, causing spatial flow-field navigation to steer approaching herbivore swarms away from the defended plant patch.

---

## Appendix: Engine Implementation & Schema Mappings

For software engineers and data interface developers, this section maps the mathematical formulation above to concrete data schemas and system modules in the PHIDS codebase.

### Schema Definitions (`src/phids/api/schemas/species.py` & `triggers.py`)

```python
class PassiveDefensesSchema(StrictBaseModel):
    """Constitutive morphological defenses of a flora species."""

    mechanical_damage_per_bite: float = Field(default=0.0, ge=0.0)
    digestibility_modifier: float = Field(default=1.0, ge=0.0, le=1.0)


class ResourceWithdrawalAction(StrictBaseModel):
    """Action configuring rate-limited phloem nutrient translocation."""

    type: Literal["resource_withdrawal"] = "resource_withdrawal"
    apparent_nutrition_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    withdrawal_duration: int = Field(default=5, ge=1)
```

### Component State (`src/phids/engine/components/plant.py`)

```python
@dataclass(slots=True)
class PlantComponent:
    apparent_nutrition_factor: float = 1.0
    target_nutrition_factor: float = 1.0
    translocation_rate: float = 0.2
    withdrawal_ticks_remaining: int = 0
```

### System Execution Pipeline (`src/phids/engine/systems/lifecycle.py`)

```python
# Phloem translocation update during lifecycle tick
if plant.withdrawal_ticks_remaining > 0:
    plant.withdrawal_ticks_remaining -= 1
    plant.apparent_nutrition_factor += (
        plant.target_nutrition_factor - plant.apparent_nutrition_factor
    ) * plant.translocation_rate
else:
    plant.apparent_nutrition_factor += (
        1.0 - plant.apparent_nutrition_factor
    ) * plant.translocation_rate
```
