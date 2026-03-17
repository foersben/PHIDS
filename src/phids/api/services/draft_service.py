"""Draft-state mutation service for PHIDS scenario-builder workflows.

This module concentrates all imperative mutation procedures applied to the UI draft state into a
single service boundary. The service preserves the existing biological and algorithmic invariants
of the builder pipeline: species-id compaction after deletions, diet-matrix resizing, trigger-rule
reference remapping, condition-tree pruning, and placement-ledger updates. By externalizing these
operations from the DraftState container, the architecture separates mutable orchestration from
state representation while maintaining deterministic scenario construction semantics required by
Rule-of-16 bounded model editing.
"""

from __future__ import annotations

import dataclasses
import logging
from copy import deepcopy

from phids.api.ui_state import (
    DraftState,
    PlacedPlant,
    PlacedSwarm,
    SubstanceDefinition,
    TriggerRule,
    _condition_node_at_path,
    _legacy_signal_ids_to_activation_condition,
    _parse_condition_path,
    _prune_empty_condition_groups,
    _remap_condition_references,
)

logger = logging.getLogger(__name__)


class DraftService:
    """Mutation orchestrator for DraftState lifecycle editing operations.

    The service applies deterministic in-place mutations to a supplied ``DraftState`` instance.
    Each method is designed for route-level command semantics where the draft is explicit input,
    allowing callers to control when and where mutation occurs while reusing one canonical
    implementation of matrix compaction and trigger-tree maintenance.
    """

    @staticmethod
    def _is_truthy_flag(value: str | bool) -> bool:
        """Interpret HTML-form boolean payloads as deterministic Python truth values.

        Args:
            value: Raw route payload representing a checkbox or toggle state.

        Returns:
            True when the submitted value represents the affirmative state.
        """
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "on")

    def _find_substance_index(self, draft: DraftState, substance_id: int) -> int | None:
        """Locate the list index for one substance identifier.

        Args:
            draft: Draft state whose substance registry is searched.
            substance_id: Substance identifier to resolve.

        Returns:
            The list index of the matching substance definition, or ``None`` if absent.
        """
        return next(
            (
                i
                for i, substance in enumerate(draft.substance_definitions)
                if substance.substance_id == substance_id
            ),
            None,
        )

    def _resize_diet_matrix(self, draft: DraftState) -> None:
        """Resize the diet matrix to match current herbivore and flora list lengths.

        Args:
            draft: Draft state whose matrix dimensions are compacted or extended.
        """
        n_herbivore = len(draft.herbivore_species)
        n_flora = len(draft.flora_species)

        while len(draft.diet_matrix) < n_herbivore:
            draft.diet_matrix.append([False] * n_flora)
        draft.diet_matrix = draft.diet_matrix[:n_herbivore]
        for row in draft.diet_matrix:
            while len(row) < n_flora:
                row.append(False)
            del row[n_flora:]

    def rebuild_species_ids(self, draft: DraftState) -> None:
        """Reassign sequential species identifiers after species-list mutations.

        Args:
            draft: Draft state whose species collections require index compaction.
        """
        from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams

        draft.flora_species = [
            fp.model_copy(update={"species_id": i})
            for i, fp in enumerate(draft.flora_species)
            if isinstance(fp, FloraSpeciesParams)
        ]
        draft.herbivore_species = [
            pp.model_copy(update={"species_id": i})
            for i, pp in enumerate(draft.herbivore_species)
            if isinstance(pp, HerbivoreSpeciesParams)
        ]

    def update_biotope(
        self,
        draft: DraftState,
        *,
        grid_width: int,
        grid_height: int,
        max_ticks: int,
        tick_rate_hz: float,
        wind_x: float,
        wind_y: float,
        num_signals: int,
        num_toxins: int,
        z2_flora_species_extinction: int,
        z4_herbivore_species_extinction: int,
        z6_max_total_flora_energy: float,
        z7_max_total_herbivore_population: int,
        mycorrhizal_inter_species: bool,
        mycorrhizal_connection_cost: float,
        mycorrhizal_growth_interval_ticks: int,
        mycorrhizal_signal_velocity: int,
    ) -> bool:
        """Normalize and persist global biotope parameters into the draft.

        Args:
            draft: Draft state mutated in place.
            grid_width: Requested biotope width.
            grid_height: Requested biotope height.
            max_ticks: Requested simulation tick horizon.
            tick_rate_hz: Requested UI stream rate.
            wind_x: Requested uniform wind x-component.
            wind_y: Requested uniform wind y-component.
            num_signals: Requested number of signal layers.
            num_toxins: Requested number of toxin layers.
            z2_flora_species_extinction: Requested species-specific flora-extinction termination rule.
            z4_herbivore_species_extinction: Requested species-specific herbivore-extinction rule.
            z6_max_total_flora_energy: Requested upper bound for total flora energy termination.
            z7_max_total_herbivore_population: Requested upper bound for herbivore population
                termination.
            mycorrhizal_inter_species: Requested root-link species policy.
            mycorrhizal_connection_cost: Requested root-link establishment cost.
            mycorrhizal_growth_interval_ticks: Requested root-growth interval.
            mycorrhizal_signal_velocity: Requested root-network signal velocity.

        Returns:
            ``True`` when at least one submitted scalar required clamping.
        """
        clamped_grid_width = max(10, min(80, grid_width))
        clamped_grid_height = max(10, min(80, grid_height))
        clamped_max_ticks = max(1, max_ticks)
        clamped_tick_rate_hz = max(0.1, tick_rate_hz)
        clamped_num_signals = max(1, min(16, num_signals))
        clamped_num_toxins = max(1, min(16, num_toxins))
        clamped_z2 = max(-1, min(15, z2_flora_species_extinction))
        clamped_z4 = max(-1, min(15, z4_herbivore_species_extinction))
        clamped_z6 = max(-1.0, z6_max_total_flora_energy)
        clamped_z7 = max(-1, z7_max_total_herbivore_population)
        clamped_connection_cost = max(0.0, mycorrhizal_connection_cost)
        clamped_growth_interval = max(1, min(256, mycorrhizal_growth_interval_ticks))
        clamped_signal_velocity = max(1, mycorrhizal_signal_velocity)

        draft.grid_width = clamped_grid_width
        draft.grid_height = clamped_grid_height
        draft.max_ticks = clamped_max_ticks
        draft.tick_rate_hz = clamped_tick_rate_hz
        draft.wind_x = wind_x
        draft.wind_y = wind_y
        draft.num_signals = clamped_num_signals
        draft.num_toxins = clamped_num_toxins
        draft.z2_flora_species_extinction = clamped_z2
        draft.z4_herbivore_species_extinction = clamped_z4
        draft.z6_max_total_flora_energy = clamped_z6
        draft.z7_max_total_herbivore_population = clamped_z7
        draft.mycorrhizal_inter_species = mycorrhizal_inter_species
        draft.mycorrhizal_connection_cost = clamped_connection_cost
        draft.mycorrhizal_growth_interval_ticks = clamped_growth_interval
        draft.mycorrhizal_signal_velocity = clamped_signal_velocity

        return any(
            (
                clamped_grid_width != grid_width,
                clamped_grid_height != grid_height,
                clamped_max_ticks != max_ticks,
                clamped_tick_rate_hz != tick_rate_hz,
                clamped_num_signals != num_signals,
                clamped_num_toxins != num_toxins,
                clamped_z2 != z2_flora_species_extinction,
                clamped_z4 != z4_herbivore_species_extinction,
                clamped_z6 != z6_max_total_flora_energy,
                clamped_z7 != z7_max_total_herbivore_population,
                clamped_connection_cost != mycorrhizal_connection_cost,
                clamped_growth_interval != mycorrhizal_growth_interval_ticks,
                clamped_signal_velocity != mycorrhizal_signal_velocity,
            )
        )

    def add_flora(self, draft: DraftState, params: object) -> None:
        """Append one flora species and expand dependent matrix state.

        Args:
            draft: Draft state mutated in place.
            params: Flora species parameter object.
        """
        draft.flora_species.append(params)
        self.rebuild_species_ids(draft)
        self._resize_diet_matrix(draft)
        logger.debug(
            "Draft flora added (species_id=%s, total_flora=%d)",
            getattr(params, "species_id", "?"),
            len(draft.flora_species),
        )

    def remove_flora(self, draft: DraftState, species_id: int) -> None:
        """Remove one flora species and compact all dependent references.

        Args:
            draft: Draft state mutated in place.
            species_id: Flora species identifier to remove.

        Raises:
            ValueError: No flora species with the requested identifier exists.
        """
        from phids.api.schemas import FloraSpeciesParams

        idx = next(
            (
                i
                for i, fp in enumerate(draft.flora_species)
                if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id
            ),
            None,
        )
        if idx is None:
            raise ValueError(f"Flora species_id {species_id} not found.")

        del draft.flora_species[idx]
        for row in draft.diet_matrix:
            if idx < len(row):
                del row[idx]

        new_rules: list[TriggerRule] = []
        for rule in draft.trigger_rules:
            if rule.flora_species_id == species_id:
                continue
            new_rule = dataclasses.replace(rule)
            if new_rule.flora_species_id > species_id:
                new_rule.flora_species_id -= 1
            new_rules.append(new_rule)
        draft.trigger_rules = new_rules

        draft.initial_plants = [p for p in draft.initial_plants if p.species_id != species_id]
        self.rebuild_species_ids(draft)
        self._resize_diet_matrix(draft)
        logger.debug(
            "Draft flora removed (species_id=%d, total_flora=%d, remaining_trigger_rules=%d)",
            species_id,
            len(draft.flora_species),
            len(draft.trigger_rules),
        )

    def add_herbivore(self, draft: DraftState, params: object) -> None:
        """Append one herbivore species and expand dependent matrix state.

        Args:
            draft: Draft state mutated in place.
            params: Herbivore species parameter object.
        """
        draft.herbivore_species.append(params)
        self.rebuild_species_ids(draft)
        self._resize_diet_matrix(draft)
        logger.debug(
            "Draft herbivore added (species_id=%s, total_herbivores=%d)",
            getattr(params, "species_id", "?"),
            len(draft.herbivore_species),
        )

    def remove_herbivore(self, draft: DraftState, species_id: int) -> None:
        """Remove one herbivore species and compact all dependent references.

        Args:
            draft: Draft state mutated in place.
            species_id: Herbivore species identifier to remove.

        Raises:
            ValueError: No herbivore species with the requested identifier exists.
        """
        from phids.api.schemas import HerbivoreSpeciesParams

        idx = next(
            (
                i
                for i, pp in enumerate(draft.herbivore_species)
                if isinstance(pp, HerbivoreSpeciesParams) and pp.species_id == species_id
            ),
            None,
        )
        if idx is None:
            raise ValueError(f"Herbivore species_id {species_id} not found.")

        del draft.herbivore_species[idx]
        if idx < len(draft.diet_matrix):
            del draft.diet_matrix[idx]

        new_rules: list[TriggerRule] = []
        for rule in draft.trigger_rules:
            if rule.herbivore_species_id == species_id:
                continue
            new_rule = dataclasses.replace(rule)
            if new_rule.herbivore_species_id > species_id:
                new_rule.herbivore_species_id -= 1
            new_rule.activation_condition = _remap_condition_references(
                deepcopy(new_rule.activation_condition),
                removed_herbivore_id=species_id,
            )
            new_rules.append(new_rule)
        draft.trigger_rules = new_rules

        draft.initial_swarms = [s for s in draft.initial_swarms if s.species_id != species_id]
        self.rebuild_species_ids(draft)
        self._resize_diet_matrix(draft)
        logger.debug(
            "Draft herbivore removed (species_id=%d, total_herbivores=%d, remaining_trigger_rules=%d)",
            species_id,
            len(draft.herbivore_species),
            len(draft.trigger_rules),
        )

    def add_substance(
        self,
        draft: DraftState,
        *,
        name: str,
        is_toxin: str | bool = False,
        lethal: str | bool = False,
        repellent: str | bool = False,
        synthesis_duration: int = 3,
        aftereffect_ticks: int = 0,
        lethality_rate: float = 0.0,
        repellent_walk_ticks: int = 3,
        energy_cost_per_tick: float = 1.0,
        irreversible: str | bool = False,
    ) -> SubstanceDefinition:
        """Append one substance definition to the bounded registry.

        Args:
            draft: Draft state mutated in place.
            name: Operator-facing substance label.
            is_toxin: Substance class toggle.
            lethal: Lethal-toxin toggle.
            repellent: Repellent-toxin toggle.
            synthesis_duration: Requested synthesis latency.
            aftereffect_ticks: Requested persistence duration after deactivation.
            lethality_rate: Requested lethal damage rate.
            repellent_walk_ticks: Requested repel walk duration.
            energy_cost_per_tick: Requested per-tick maintenance cost.
            irreversible: Irreversible activation toggle.

        Returns:
            The created ``SubstanceDefinition`` entry.

        Raises:
            ValueError: The Rule of 16 ceiling for substances has been reached.
        """
        if len(draft.substance_definitions) >= 16:
            raise ValueError("Rule of 16: maximum substances reached.")

        definition = SubstanceDefinition(
            substance_id=len(draft.substance_definitions),
            name=name,
            is_toxin=self._is_truthy_flag(is_toxin),
            lethal=self._is_truthy_flag(lethal),
            repellent=self._is_truthy_flag(repellent),
            synthesis_duration=max(1, synthesis_duration),
            aftereffect_ticks=max(0, aftereffect_ticks),
            lethality_rate=max(0.0, lethality_rate),
            repellent_walk_ticks=max(0, repellent_walk_ticks),
            energy_cost_per_tick=max(0.0, energy_cost_per_tick),
            irreversible=self._is_truthy_flag(irreversible),
        )
        draft.substance_definitions.append(definition)
        logger.debug(
            "Draft substance added (substance_id=%d, name=%s, is_toxin=%s, total_substances=%d)",
            definition.substance_id,
            definition.name,
            definition.is_toxin,
            len(draft.substance_definitions),
        )
        return definition

    def update_substance(
        self,
        draft: DraftState,
        substance_id: int,
        *,
        name: str | None = None,
        type_label: str | None = None,
        synthesis_duration: int | None = None,
        aftereffect_ticks: int | None = None,
        lethality_rate: float | None = None,
        repellent_walk_ticks: int | None = None,
        energy_cost_per_tick: float | None = None,
        irreversible: str | bool | None = None,
    ) -> SubstanceDefinition:
        """Patch one substance definition in place.

        Args:
            draft: Draft state mutated in place.
            substance_id: Substance identifier to modify.
            name: Optional replacement name.
            type_label: Optional UI type label controlling toxin flags.
            synthesis_duration: Optional replacement synthesis latency.
            aftereffect_ticks: Optional replacement persistence duration.
            lethality_rate: Optional replacement lethal damage rate.
            repellent_walk_ticks: Optional replacement repel walk duration.
            energy_cost_per_tick: Optional replacement maintenance cost.
            irreversible: Optional replacement irreversible flag.

        Returns:
            The mutated ``SubstanceDefinition`` entry.

        Raises:
            ValueError: No substance with the requested identifier exists.
        """
        idx = self._find_substance_index(draft, substance_id)
        if idx is None:
            raise ValueError(f"Substance {substance_id} not found.")

        definition = draft.substance_definitions[idx]
        if name is not None:
            definition.name = name
        if type_label is not None:
            definition.is_toxin = type_label in (
                "Lethal Toxin",
                "Repellent Toxin",
                "Repelling Toxin",
                "Toxin",
            )
            definition.lethal = type_label == "Lethal Toxin"
            definition.repellent = type_label in ("Repellent Toxin", "Repelling Toxin")
        if synthesis_duration is not None:
            definition.synthesis_duration = max(1, synthesis_duration)
        if aftereffect_ticks is not None:
            definition.aftereffect_ticks = max(0, aftereffect_ticks)
        if lethality_rate is not None:
            definition.lethality_rate = max(0.0, lethality_rate)
        if repellent_walk_ticks is not None:
            definition.repellent_walk_ticks = max(0, repellent_walk_ticks)
        if energy_cost_per_tick is not None:
            definition.energy_cost_per_tick = max(0.0, energy_cost_per_tick)
        if irreversible is not None:
            definition.irreversible = self._is_truthy_flag(irreversible)

        logger.debug(
            "Draft substance updated (substance_id=%d, name=%s, is_toxin=%s)",
            substance_id,
            definition.name,
            definition.is_toxin,
        )
        return definition

    def remove_substance(self, draft: DraftState, substance_id: int) -> None:
        """Remove one substance definition and compact all dependent references.

        Args:
            draft: Draft state mutated in place.
            substance_id: Substance identifier to remove.

        Raises:
            ValueError: No substance with the requested identifier exists.
        """
        idx = self._find_substance_index(draft, substance_id)
        if idx is None:
            raise ValueError(f"Substance {substance_id} not found.")

        del draft.substance_definitions[idx]
        for new_id, definition in enumerate(draft.substance_definitions):
            definition.substance_id = new_id
            if definition.precursor_signal_id == substance_id:
                definition.precursor_signal_id = -1
            elif definition.precursor_signal_id > substance_id:
                definition.precursor_signal_id -= 1

        remaining_rules: list[TriggerRule] = []
        removed_rules = 0
        for rule in draft.trigger_rules:
            if rule.substance_id == substance_id:
                removed_rules += 1
                continue
            new_rule = dataclasses.replace(rule)
            if new_rule.substance_id > substance_id:
                new_rule.substance_id -= 1
            new_rule.activation_condition = _remap_condition_references(
                deepcopy(new_rule.activation_condition),
                removed_substance_id=substance_id,
            )
            remaining_rules.append(new_rule)
        draft.trigger_rules = remaining_rules

        logger.debug(
            "Draft substance removed (substance_id=%d, total_substances=%d, remaining_trigger_rules=%d, removed_trigger_rules=%d)",
            substance_id,
            len(draft.substance_definitions),
            len(draft.trigger_rules),
            removed_rules,
        )

    def set_diet_compatibility(
        self,
        draft: DraftState,
        herbivore_idx: int,
        flora_idx: int,
        compatible: str = "toggle",
    ) -> bool | None:
        """Toggle or assign one herbivore-flora edibility matrix cell.

        Args:
            draft: Draft state mutated in place.
            herbivore_idx: Herbivore row index.
            flora_idx: Flora column index.
            compatible: Requested boolean state or the literal ``"toggle"``.

        Returns:
            The updated boolean cell value, or ``None`` when the indices are out of range.
        """
        if herbivore_idx >= len(draft.diet_matrix) or herbivore_idx < 0:
            return None
        if flora_idx >= len(draft.diet_matrix[herbivore_idx]) or flora_idx < 0:
            return None

        if compatible == "toggle":
            draft.diet_matrix[herbivore_idx][flora_idx] = not draft.diet_matrix[herbivore_idx][
                flora_idx
            ]
        else:
            draft.diet_matrix[herbivore_idx][flora_idx] = self._is_truthy_flag(compatible)
        return draft.diet_matrix[herbivore_idx][flora_idx]

    def add_trigger_rule(
        self,
        draft: DraftState,
        flora_species_id: int,
        herbivore_species_id: int,
        substance_id: int,
        min_herbivore_population: int = 5,
        activation_condition: dict[str, object] | None = None,
        required_signal_ids: list[int] | None = None,
    ) -> None:
        """Append one trigger rule to the draft trigger ledger.

        Args:
            draft: Draft state mutated in place.
            flora_species_id: Flora species identifier.
            herbivore_species_id: Herbivore species identifier.
            substance_id: Substance identifier synthesized by the rule.
            min_herbivore_population: Minimum herbivore population threshold.
            activation_condition: Optional nested activation-condition tree.
            required_signal_ids: Optional legacy shorthand converted into tree form.
        """
        draft.trigger_rules.append(
            TriggerRule(
                flora_species_id=flora_species_id,
                herbivore_species_id=herbivore_species_id,
                substance_id=substance_id,
                min_herbivore_population=min_herbivore_population,
                activation_condition=deepcopy(
                    activation_condition
                    if activation_condition is not None
                    else _legacy_signal_ids_to_activation_condition(required_signal_ids)
                ),
            )
        )
        logger.debug(
            "Draft trigger rule added (flora_species_id=%d, herbivore_species_id=%d, substance_id=%d, total_rules=%d)",
            flora_species_id,
            herbivore_species_id,
            substance_id,
            len(draft.trigger_rules),
        )

    def remove_trigger_rule(self, draft: DraftState, index: int) -> None:
        """Remove one trigger rule by list index.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.

        Raises:
            IndexError: The requested trigger-rule index is out of range.
        """
        removed = draft.trigger_rules[index]
        del draft.trigger_rules[index]
        logger.debug(
            "Draft trigger rule removed (index=%d, flora_species_id=%d, herbivore_species_id=%d, substance_id=%d, total_rules=%d)",
            index,
            removed.flora_species_id,
            removed.herbivore_species_id,
            removed.substance_id,
            len(draft.trigger_rules),
        )

    def update_trigger_rule(
        self,
        draft: DraftState,
        index: int,
        *,
        flora_species_id: int | None = None,
        herbivore_species_id: int | None = None,
        substance_id: int | None = None,
        min_herbivore_population: int | None = None,
        activation_condition: dict[str, object] | None = None,
        required_signal_ids: list[int] | None = None,
    ) -> None:
        """Patch selected fields on one trigger rule.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            flora_species_id: Optional replacement flora species identifier.
            herbivore_species_id: Optional replacement herbivore species identifier.
            substance_id: Optional replacement substance identifier.
            min_herbivore_population: Optional replacement threshold.
            activation_condition: Optional replacement condition tree.
            required_signal_ids: Optional legacy shorthand converted into tree form.

        Raises:
            IndexError: The requested trigger-rule index is out of range.
        """
        rule = draft.trigger_rules[index]
        if flora_species_id is not None:
            rule.flora_species_id = flora_species_id
        if herbivore_species_id is not None:
            rule.herbivore_species_id = herbivore_species_id
        if substance_id is not None:
            rule.substance_id = substance_id
        if min_herbivore_population is not None:
            rule.min_herbivore_population = min_herbivore_population
        if activation_condition is not None:
            rule.activation_condition = deepcopy(activation_condition)
        elif required_signal_ids is not None:
            rule.activation_condition = _legacy_signal_ids_to_activation_condition(
                required_signal_ids
            )
        logger.debug(
            "Draft trigger rule updated (index=%d, flora_species_id=%d, herbivore_species_id=%d, substance_id=%d)",
            index,
            rule.flora_species_id,
            rule.herbivore_species_id,
            rule.substance_id,
        )

    def set_trigger_rule_activation_condition(
        self,
        draft: DraftState,
        index: int,
        condition: dict[str, object] | None,
    ) -> None:
        """Replace the full activation-condition tree for one trigger rule.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            condition: Full replacement condition tree.
        """
        draft.trigger_rules[index].activation_condition = deepcopy(condition)

    def replace_trigger_rule_condition_node(
        self,
        draft: DraftState,
        index: int,
        path: str,
        condition: dict[str, object],
    ) -> None:
        """Replace one condition node addressed by a dotted path.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            path: Dotted child index path identifying the node to replace.
            condition: Replacement node payload.

        Raises:
            IndexError: The path or parent node does not resolve to a mutable child slot.
        """
        rule = draft.trigger_rules[index]
        if not path:
            rule.activation_condition = deepcopy(condition)
            return
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to replace.")
        root = deepcopy(rule.activation_condition)
        path_indices = _parse_condition_path(path)
        parent = _condition_node_at_path(root, path_indices[:-1])
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.get("conditions")
        if not isinstance(children, list):
            raise IndexError("Condition parent has no child list.")
        child_index = path_indices[-1]
        if child_index < 0 or child_index >= len(children):
            raise IndexError("Condition node index is out of range.")
        children[child_index] = deepcopy(condition)
        rule.activation_condition = root

    def append_trigger_rule_condition_child(
        self,
        draft: DraftState,
        index: int,
        parent_path: str,
        condition: dict[str, object],
    ) -> None:
        """Append one child condition to a group node in a trigger tree.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            parent_path: Dotted path to the parent group node.
            condition: Child node payload to append.

        Raises:
            IndexError: The parent node is missing or is not a valid group node.
        """
        rule = draft.trigger_rules[index]
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to append to.")
        root = deepcopy(rule.activation_condition)
        parent = _condition_node_at_path(root, _parse_condition_path(parent_path))
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.setdefault("conditions", [])
        if not isinstance(children, list):
            raise IndexError("Condition parent has an invalid child list.")
        children.append(deepcopy(condition))
        rule.activation_condition = root

    def delete_trigger_rule_condition_node(self, draft: DraftState, index: int, path: str) -> None:
        """Delete one condition node by dotted path and prune empty groups.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            path: Dotted child index path to remove.

        Raises:
            IndexError: The path or parent node does not resolve to a removable child slot.
        """
        rule = draft.trigger_rules[index]
        if rule.activation_condition is None:
            return
        if not path:
            rule.activation_condition = None
            return
        root = deepcopy(rule.activation_condition)
        path_indices = _parse_condition_path(path)
        parent = _condition_node_at_path(root, path_indices[:-1])
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.get("conditions")
        if not isinstance(children, list):
            raise IndexError("Condition parent has no child list.")
        child_index = path_indices[-1]
        if child_index < 0 or child_index >= len(children):
            raise IndexError("Condition node index is out of range.")
        del children[child_index]
        rule.activation_condition = _prune_empty_condition_groups(root)

    def update_trigger_rule_condition_node(
        self,
        draft: DraftState,
        index: int,
        path: str,
        **fields: object,
    ) -> None:
        """Patch selected key-value fields on one condition node.

        Args:
            draft: Draft state mutated in place.
            index: Trigger-rule index in the draft list.
            path: Dotted path to the condition node.
            **fields: Replacement key-value fields merged into the node.

        Raises:
            IndexError: The trigger rule has no condition tree or path resolution fails.
        """
        rule = draft.trigger_rules[index]
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to update.")
        root = deepcopy(rule.activation_condition)
        node = _condition_node_at_path(root, _parse_condition_path(path))
        node.update(fields)
        rule.activation_condition = root

    def add_plant_placement(
        self,
        draft: DraftState,
        species_id: int,
        x: int,
        y: int,
        energy: float,
    ) -> None:
        """Append one plant placement to the draft placement ledger.

        Args:
            draft: Draft state mutated in place.
            species_id: Flora species identifier.
            x: Grid x-coordinate.
            y: Grid y-coordinate.
            energy: Initial plant energy reserve.
        """
        draft.initial_plants.append(PlacedPlant(species_id=species_id, x=x, y=y, energy=energy))
        logger.debug(
            "Draft plant placement added (species_id=%d, x=%d, y=%d, total_plants=%d)",
            species_id,
            x,
            y,
            len(draft.initial_plants),
        )

    def add_swarm_placement(
        self,
        draft: DraftState,
        species_id: int,
        x: int,
        y: int,
        population: int,
        energy: float,
    ) -> None:
        """Append one swarm placement to the draft placement ledger.

        Args:
            draft: Draft state mutated in place.
            species_id: Herbivore species identifier.
            x: Grid x-coordinate.
            y: Grid y-coordinate.
            population: Initial swarm population.
            energy: Initial swarm energy reserve.
        """
        draft.initial_swarms.append(
            PlacedSwarm(
                species_id=species_id,
                x=x,
                y=y,
                population=population,
                energy=energy,
            )
        )
        logger.debug(
            "Draft swarm placement added (species_id=%d, x=%d, y=%d, population=%d, total_swarms=%d)",
            species_id,
            x,
            y,
            population,
            len(draft.initial_swarms),
        )

    def remove_plant_placement(self, draft: DraftState, index: int) -> None:
        """Remove one plant placement by list index.

        Args:
            draft: Draft state mutated in place.
            index: Placement index to remove.

        Raises:
            IndexError: The plant placement index is out of range.
        """
        removed = draft.initial_plants[index]
        del draft.initial_plants[index]
        logger.debug(
            "Draft plant placement removed (index=%d, species_id=%d, x=%d, y=%d, total_plants=%d)",
            index,
            removed.species_id,
            removed.x,
            removed.y,
            len(draft.initial_plants),
        )

    def remove_swarm_placement(self, draft: DraftState, index: int) -> None:
        """Remove one swarm placement by list index.

        Args:
            draft: Draft state mutated in place.
            index: Placement index to remove.

        Raises:
            IndexError: The swarm placement index is out of range.
        """
        removed = draft.initial_swarms[index]
        del draft.initial_swarms[index]
        logger.debug(
            "Draft swarm placement removed (index=%d, species_id=%d, x=%d, y=%d, total_swarms=%d)",
            index,
            removed.species_id,
            removed.x,
            removed.y,
            len(draft.initial_swarms),
        )

    def clear_placements(self, draft: DraftState) -> None:
        """Clear all plant and swarm placements from the draft.

        Args:
            draft: Draft state mutated in place.
        """
        cleared_plants = len(draft.initial_plants)
        cleared_swarms = len(draft.initial_swarms)
        draft.initial_plants.clear()
        draft.initial_swarms.clear()
        logger.debug(
            "Draft placements cleared (plants=%d, swarms=%d)",
            cleared_plants,
            cleared_swarms,
        )
