"""Layer 2: Computation engine for conditional rules."""
import logging

from app.models.schemas import ConstraintSchema, ParcelSchema

logger = logging.getLogger(__name__)


class ComputationEngine:
    """Evaluate conditional rules against parcel dimensions.

    Takes Layer 1 constraints that have conditions and resolves them
    using actual parcel measurements.
    """

    def refine_constraints(
        self,
        constraints: list[ConstraintSchema],
        parcel: ParcelSchema,
        building_type: str = "SFH",
    ) -> list[ConstraintSchema]:
        """Refine constraints by evaluating conditions against parcel data."""
        refined = []
        for constraint in constraints:
            updated = self._evaluate_condition(constraint, parcel)
            refined.append(updated)

        extra = self._compute_derived(parcel, building_type, constraints)
        refined.extend(extra)

        logger.info(f"Layer 2: Refined {len(constraints)} constraints, added {len(extra)} derived")
        return refined

    def _evaluate_condition(
        self, constraint: ConstraintSchema, parcel: ParcelSchema
    ) -> ConstraintSchema:
        """Evaluate a single constraint's conditions against parcel data."""
        if constraint.parameter == "side_setback" and parcel.lot_width_ft:
            lot_width = parcel.lot_width_ft
            if lot_width < 50:
                computed_value = max(3.0, lot_width * 0.10)
                constraint.numeric_value = round(computed_value, 1)
                constraint.value = f"{constraint.numeric_value} ft"
                constraint.rule_text = f"Side Setback: {constraint.numeric_value} ft (10% of {lot_width}ft lot width, min 3ft)"
                constraint.source_layer = "computed"
                constraint.reasoning = (
                    f"Lot width is {lot_width}ft (< 50ft), so side setback = "
                    f"max(3, {lot_width} * 0.10) = {constraint.numeric_value}ft "
                    f"per LAMC Sec. {constraint.citations[0].section_number if constraint.citations else 'N/A'}"
                )

        return constraint

    def _compute_derived(
        self,
        parcel: ParcelSchema,
        building_type: str,
        existing_constraints: list[ConstraintSchema],
    ) -> list[ConstraintSchema]:
        """Compute additional constraints derived from parcel data + rules."""
        derived = []
        existing_params = {c.parameter for c in existing_constraints}

        if parcel.lot_area_sqft and "max_far" in existing_params:
            far_constraint = next(
                (c for c in existing_constraints if c.parameter == "max_far"), None
            )
            if far_constraint and far_constraint.numeric_value:
                max_floor_area = parcel.lot_area_sqft * far_constraint.numeric_value
                derived.append(ConstraintSchema(
                    category="far",
                    parameter="max_floor_area",
                    rule_text=f"Maximum Floor Area: {max_floor_area:,.0f} sqft",
                    value=f"{max_floor_area:,.0f} sqft",
                    numeric_value=round(max_floor_area, 0),
                    unit="sqft",
                    confidence=1.0,
                    source_layer="computed",
                    determination_type="deterministic",
                    citations=[c.model_copy() for c in far_constraint.citations],
                    reasoning=(
                        f"Computed from lot area ({parcel.lot_area_sqft:,.0f} sqft) × "
                        f"FAR ({far_constraint.numeric_value}) = {max_floor_area:,.0f} sqft"
                    ),
                ))

        if parcel.lot_area_sqft and "lot_area_per_unit" in existing_params:
            density_rule = next(
                (c for c in existing_constraints if c.parameter == "lot_area_per_unit"), None
            )
            if density_rule and density_rule.numeric_value and density_rule.numeric_value > 0:
                max_units = int(parcel.lot_area_sqft / density_rule.numeric_value)
                derived.append(ConstraintSchema(
                    category="density",
                    parameter="computed_max_units",
                    rule_text=f"Maximum Dwelling Units: {max_units}",
                    value=str(max_units),
                    numeric_value=float(max_units),
                    unit="units",
                    confidence=1.0,
                    source_layer="computed",
                    determination_type="deterministic",
                    citations=[c.model_copy() for c in density_rule.citations],
                    reasoning=(
                        f"Computed from lot area ({parcel.lot_area_sqft:,.0f} sqft) ÷ "
                        f"area per unit ({density_rule.numeric_value:,.0f} sqft) = {max_units} units"
                    ),
                ))

        return derived
