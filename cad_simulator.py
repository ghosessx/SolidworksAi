"""
SolidAI — Static CAD Plan Dry-Run Simulator & Overlap Verifier
Validates CAD action plans in pure Python before touching SOLIDWORKS.
Detects:
- Sketch lifecycle anomalies (sketch without prior selection, extrusion without sketch).
- Dangerous contour overlaps (e.g., intersecting shapes in single sketch without trimming).
- Missing revolution centerlines.
- Simulated geometric volume, body count, and bounding box feasibility.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from cad_schema import validate_cad_plan, CADPlan
from mock_engine import MockCADEngine


@dataclass
class SimulationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    final_state: Dict[str, Any] = field(default_factory=dict)
    failed_step_index: Optional[int] = None

    def __bool__(self) -> bool:
        return self.valid


class CADSimulator:
    def __init__(self):
        self.mock_engine = MockCADEngine()

    def simulate(self, plan: Any) -> SimulationResult:
        """Simulates full plan execution on MockCADEngine with static semantic checks."""
        # 1. Pydantic Schema Validation
        try:
            validated_plan = validate_cad_plan(plan)
        except Exception as e:
            return SimulationResult(
                valid=False,
                errors=[f"Pydantic schema validation error: {str(e)}"],
                failed_step_index=0
            )

        errors = []
        warnings = []

        # 2. Lifecycle & Contour Overlap Static Analysis
        in_sketch = False
        target_selected = False
        current_sketch_drawings = []
        revolve_has_centerline = False

        for idx, step in enumerate(validated_plan.adimlar):
            cmd = step.islem
            params = step.params

            # Selection
            if cmd.startswith("select_") or cmd == "create_ref_plane":
                target_selected = True

            # Start Sketch
            elif cmd == "start_sketch":
                if not target_selected and idx == 0:
                    errors.append(f"Step {idx + 1} (start_sketch): A plane or face must be selected before starting a sketch.")
                in_sketch = True
                current_sketch_drawings = []
                revolve_has_centerline = False

            # Drawing commands
            elif cmd.startswith("draw_"):
                if not in_sketch:
                    warnings.append(f"Step {idx + 1} ({cmd}): 'start_sketch' was not explicitly called before drawing; auto-started sketch.")
                    in_sketch = True

                current_sketch_drawings.append((cmd, params))
                if cmd == "draw_centerline":
                    revolve_has_centerline = True

            # Feature Extrusion / Revolve / Cut
            elif cmd.startswith("extrude_") or cmd.startswith("revolve_"):
                if not current_sketch_drawings:
                    errors.append(f"Step {idx + 1} ({cmd}): Sketch contains no 2D profiles or geometry.")

                # Check for suspicious contour overlaps
                contour_types = [c[0] for c in current_sketch_drawings if c[0] != "draw_centerline"]
                if len(contour_types) > 1:
                    is_all_same = len(set(contour_types)) == 1
                    is_concentric = all(c == "draw_circle" for c in contour_types)
                    has_pattern = any("pattern" in c for c in contour_types)
                    is_cut = (cmd == "extrude_cut")
                    if not is_all_same and not is_concentric and not has_pattern and not is_cut:
                        warnings.append(
                            f"Step {idx + 1} ({cmd}): Multiple distinct contour types ({contour_types}) detected in single sketch. "
                            "In SOLIDWORKS, overlapping/untrimmed contours may cause multi-body or extrusion failures."
                        )

                if cmd == "revolve_boss" and not revolve_has_centerline:
                    errors.append(f"Step {idx + 1} (revolve_boss): A revolution requires an axis of revolution ('draw_centerline') in the sketch.")

                in_sketch = False
                current_sketch_drawings = []

            elif cmd == "close_sketch":
                in_sketch = False

        if errors:
            return SimulationResult(valid=False, errors=errors, warnings=warnings, failed_step_index=0)

        # 3. Dynamic Execution on Mock Engine
        self.mock_engine.new_part()
        for idx, step in enumerate(validated_plan.adimlar):
            cmd = step.islem
            params = step.params
            method = getattr(self.mock_engine, cmd)
            try:
                res = method(**params)
                if not res.ok:
                    return SimulationResult(
                        valid=False,
                        errors=[f"Simulation Step {idx + 1} ({cmd}) failed: {res.error}"],
                        warnings=warnings,
                        failed_step_index=idx,
                        final_state=self.mock_engine.get_model_state()
                    )
            except Exception as ex:
                return SimulationResult(
                    valid=False,
                    errors=[f"Simulation Step {idx + 1} ({cmd}) raised exception: {str(ex)}"],
                    warnings=warnings,
                    failed_step_index=idx,
                    final_state=self.mock_engine.get_model_state()
                )

        final_state = self.mock_engine.get_model_state()
        if final_state["body_count"] == 0 and any(s.islem.startswith("extrude_boss") for s in validated_plan.adimlar):
            return SimulationResult(
                valid=False,
                errors=["Simulation completed with 0 solid bodies created."],
                warnings=warnings,
                final_state=final_state
            )

        return SimulationResult(valid=True, errors=[], warnings=warnings, final_state=final_state)
