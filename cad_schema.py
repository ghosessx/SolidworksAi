"""
SolidAI — CAD Action Plan Schema & Validation with Pydantic
Enforces strict structural rules, typed parameters, and backwards compatibility.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


VALID_ENGINE_OPERATIONS = {
    # Selection
    "select_plane",
    "select_face",
    "select_top_face",
    "select_face_by_ray",
    "create_ref_plane",
    "select_ref_plane",
    # Sketch
    "start_sketch",
    "close_sketch",
    "draw_circle",
    "draw_center_rectangle",
    "draw_corner_rectangle",
    "draw_rotated_rectangle",
    "draw_l_profile",
    "draw_line_chain",
    "draw_centerline",
    "draw_circular_hole_pattern",
    "draw_rectangular_hole_pattern",
    "draw_slot",
    "draw_polygon",
    "draw_hexagon",
    "draw_counterbore_hole",
    "draw_countersink_hole",
    "draw_lightening_pocket",
    "draw_linear_hole_pattern",
    "draw_stiffening_rib",
    # Features
    "extrude_boss",
    "extrude_cut",
    "revolve_boss",
    "revolve_cut",
    "apply_chamfer",
    "apply_fillet",
    "apply_fillet_all_last_feature",
    "create_hole_wizard",
    "create_rectangular_hole_wizard",
    "circular_pattern_last_feature",
    "shell_body"
}


class CADStep(BaseModel):
    islem: str = Field(..., description="CAD engine operation method")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")

    @field_validator("islem")
    @classmethod
    def validate_islem(cls, v: str) -> str:
        clean_v = v.strip()
        if clean_v not in VALID_ENGINE_OPERATIONS:
            raise ValueError(f"Invalid CAD operation: '{clean_v}'. Supported operations: {sorted(VALID_ENGINE_OPERATIONS)}")
        return clean_v

    @model_validator(mode="before")
    @classmethod
    def handle_parametreler_alias(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Support English 'action' or 'operation' as aliases for 'islem'
            if "islem" not in values:
                for k in ["action", "operation", "command", "method"]:
                    if k in values:
                        values["islem"] = values[k]
                        break
            if "params" not in values:
                for k in ["parametreler", "parameters", "args", "arguments"]:
                    if k in values:
                        values["params"] = values[k]
                        break
                else:
                    values["params"] = {}
        return values


class CADPlan(BaseModel):
    parca_adi: str = Field(default="Mechanical Part", description="Part or model name")
    tasarim_mantigi: str = Field(default="", description="Design rationale and step summary")
    muhendislik_dusuncesi: Optional[Any] = Field(default=None, description="Engineering analysis & Chain-of-Thought reasoning")
    adimlar: List[CADStep] = Field(..., min_length=1, description="Sequential CAD steps list")

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Support English keys as primary/fallback aliases
            if "parca_adi" not in values and "part_name" in values:
                values["parca_adi"] = values["part_name"]
            if "tasarim_mantigi" not in values and "design_logic" in values:
                values["tasarim_mantigi"] = values["design_logic"]
            if "muhendislik_dusuncesi" not in values:
                for k in ["engineering_reasoning", "design_thinking", "muhendislik_analizi", "analiz", "reasoning"]:
                    if k in values:
                        values["muhendislik_dusuncesi"] = values[k]
                        break
            if "adimlar" not in values and "steps" in values:
                values["adimlar"] = values["steps"]
        return values


def validate_cad_plan(plan_data: Any) -> CADPlan:
    """Validates raw dict or JSON plan against CADPlan schema."""
    if isinstance(plan_data, dict):
        return CADPlan.model_validate(plan_data)
    elif isinstance(plan_data, CADPlan):
        return plan_data
    else:
        raise TypeError(f"Plan data must be dict or CADPlan, got: {type(plan_data)}")
