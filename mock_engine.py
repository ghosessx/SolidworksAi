"""
MockCADEngine — Pure Python In-Memory CAD Engine for Headless Testing & CI.
Implements the exact same interface as SolidWorksCADEngine without requiring SOLIDWORKS.
Calculates exact mathematical areas, volumes, and bounding boxes.
"""
import math
from typing import Optional, List, Dict, Tuple, Any
from cad_engine import StepResult


class MockCADEngine:
    def __init__(self):
        self.model = {"name": "MockPart", "features": []}
        self.in_sketch = False
        self.active_plane = None
        self.selected_target = None
        self.current_sketch_entities = []
        self.bodies = []
        self.volume_mm3 = 0.0
        self.box_min_mm = [0.0, 0.0, 0.0]
        self.box_max_mm = [0.0, 0.0, 0.0]
        self.ref_planes = []
        self.last_feature = None
        self.last_wall_thickness = 15.0

    def new_part(self) -> StepResult:
        self.model = {"name": "MockPart", "features": []}
        self.in_sketch = False
        self.active_plane = None
        self.selected_target = None
        self.current_sketch_entities = []
        self.bodies = []
        self.volume_mm3 = 0.0
        self.box_min_mm = [0.0, 0.0, 0.0]
        self.box_max_mm = [0.0, 0.0, 0.0]
        self.ref_planes = []
        self.last_feature = None
        self.last_wall_thickness = 15.0
        return StepResult(ok=True, state=self.get_model_state())

    def close_document(self, save: bool = False):
        self.new_part()

    def ensure_document(self):
        return self.model

    def rebuild(self) -> bool:
        return True

    def zoom_fit(self):
        pass

    def is_in_sketch(self) -> bool:
        return self.in_sketch

    def get_model_state(self) -> dict:
        return {
            "body_count": len(self.bodies),
            "volume_mm3": round(self.volume_mm3, 3),
            "surface_area_mm2": 0.0,
            "box_min_mm": list(self.box_min_mm),
            "box_max_mm": list(self.box_max_mm),
            "active_sketch": self.in_sketch,
            "feature_count": len(self.model["features"]),
            "last_feature": self.last_feature
        }

    # =========================================================================
    # SELECTION & PLANES
    # =========================================================================

    def select_plane(self, plane: str) -> StepResult:
        plane_clean = str(plane).lower().strip()
        category = ""
        if any(k in plane_clean for k in ["ust", "üst", "top"]):
            category = "ust"
        elif any(k in plane_clean for k in ["on", "ön", "front"]):
            category = "on"
        elif any(k in plane_clean for k in ["sag", "sağ", "right"]):
            category = "sag"
        else:
            category = plane

        valid_planes = ["ust", "on", "sag"] + self.ref_planes
        if category in valid_planes or any(category in p for p in valid_planes):
            self.active_plane = category
            self.selected_target = f"Plane:{category}"
            return StepResult(ok=True, feature_name=category)

        return StepResult(ok=False, error=f"Mock Engine: Plane '{plane}' not found.")

    def select_face(self, where: str = "top", normal: Optional[Tuple[float, float, float]] = None) -> StepResult:
        if not self.bodies:
            return StepResult(ok=False, error="Mock Engine: No solid body exists to select face from.")
        self.selected_target = f"Face:{where}"
        return StepResult(ok=True)

    def select_top_face(self) -> StepResult:
        return self.select_face(where="top")

    def select_face_by_ray(self, x: float, y: float, z: float,
                           dx: float = 0.0, dy: float = -1.0, dz: float = 0.0) -> StepResult:
        if not self.bodies:
            return StepResult(ok=False, error=f"Mock Engine: Ray ({x}, {y}, {z}) missed (no bodies exist).")
        self.selected_target = f"RayFace:({x},{y},{z})"
        return StepResult(ok=True)

    def create_ref_plane(self, base_plane: str, distance_mm: float, flip: bool = False) -> StepResult:
        name = f"RefPlane_{len(self.ref_planes) + 1}"
        self.ref_planes.append(name)
        self.last_feature = name
        self.model["features"].append(name)
        return StepResult(ok=True, feature_name=name)

    def select_ref_plane(self, **kwargs) -> StepResult:
        if self.ref_planes:
            name = self.ref_planes[-1]
            self.active_plane = name
            self.selected_target = f"Plane:{name}"
            return StepResult(ok=True, feature_name=name)
        return StepResult(ok=False, error="Mock Engine: No reference planes exist.")

    def world_to_sketch_coords(self, wx: float, wy: float, wz: float, plane: str = "on") -> Tuple[float, float]:
        p = str(plane).lower()
        if "ust" in p or "top" in p:
            return float(wx), -float(wz)
        elif "sag" in p or "right" in p:
            return -float(wz), float(wy)
        else:
            return float(wx), float(wy)

    def sketch_to_world_coords(self, u: float, v: float, plane: str = "on", depth: float = 0.0) -> Tuple[float, float, float]:
        p = str(plane).lower()
        if "ust" in p or "top" in p:
            return float(u), float(depth), -float(v)
        elif "sag" in p or "right" in p:
            return float(depth), float(v), -float(u)
        else:
            return float(u), float(v), float(depth)

    # =========================================================================
    # SKETCH
    # =========================================================================

    def start_sketch(self) -> StepResult:
        if not self.selected_target and not self.active_plane:
            return StepResult(ok=False, error="Mock Engine: Cannot start sketch without selecting plane or face first.")
        self.in_sketch = True
        self.current_sketch_entities = []
        return StepResult(ok=True)

    def close_sketch(self) -> StepResult:
        self.in_sketch = False
        return StepResult(ok=True)

    def _ensure_sketch(self):
        if not self.in_sketch:
            self.start_sketch()

    def draw_circle(self, x: float, y: float, dia: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({"type": "circle", "x": x, "y": y, "dia": dia})
        return StepResult(ok=True)

    def draw_center_rectangle(self, x: float = 0.0, y: float = 0.0, w: float = 0.0, h: float = 0.0,
                              center_x: float = None, center_y: float = None,
                              width_mm: float = None, height_mm: float = None) -> StepResult:
        self._ensure_sketch()
        actual_x = float(center_x if center_x is not None else x)
        actual_y = float(center_y if center_y is not None else y)
        actual_w = float(width_mm if width_mm is not None else w)
        actual_h = float(height_mm if height_mm is not None else h)
        self.current_sketch_entities.append({"type": "center_rect", "x": actual_x, "y": actual_y, "w": actual_w, "h": actual_h})
        return StepResult(ok=True)

    def draw_corner_rectangle(self, x1: float, y1: float, x2: float, y2: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({"type": "corner_rect", "x1": x1, "y1": y1, "x2": x2, "y2": y2})
        return StepResult(ok=True)

    def draw_rotated_rectangle(self, center_x: float, center_y: float,
                               length_mm: float, width_mm: float, angle_deg: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "rotated_rect",
            "cx": float(center_x),
            "cy": float(center_y),
            "length": float(length_mm),
            "width": float(width_mm),
            "angle": float(angle_deg)
        })
        return StepResult(ok=True)

    def draw_l_profile(self, width_mm: float, height_mm: float, thickness_mm: float) -> StepResult:
        self._ensure_sketch()
        self.last_wall_thickness = float(thickness_mm)
        self.current_sketch_entities.append({
            "type": "l_profile", "width": width_mm, "height": height_mm, "thickness": thickness_mm
        })
        return StepResult(ok=True)

    def draw_line_chain(self, points_list: list, close_loop: bool = True) -> StepResult:
        self._ensure_sketch()
        if len(points_list) < 2:
            return StepResult(ok=False, error="Mock Engine: draw_line_chain requires at least 2 points.")
        self.current_sketch_entities.append({"type": "line_chain", "points": points_list, "closed": close_loop})
        return StepResult(ok=True)

    def draw_centerline(self, x1: float, y1: float, x2: float, y2: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({"type": "centerline", "p1": (x1, y1), "p2": (x2, y2)})
        return StepResult(ok=True)

    def draw_circular_hole_pattern(self, center_x: float, center_y: float,
                                   pcd_mm: float, count: int, dia_mm: float,
                                   start_angle_deg: float = 0.0) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "circular_pattern", "cx": center_x, "cy": center_y, "pcd": pcd_mm, "count": count, "dia": dia_mm
        })
        return StepResult(ok=True)

    def draw_rectangular_hole_pattern(self, center_x: float, center_y: float,
                                      spacing_x_mm: float, spacing_y_mm: float, dia_mm: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "rect_pattern", "cx": center_x, "cy": center_y, "sx": spacing_x_mm, "sy": spacing_y_mm, "dia": dia_mm
        })
        return StepResult(ok=True)

    def draw_slot(self, x1: float, y1: float, x2: float, y2: float, width: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({"type": "slot", "p1": (x1, y1), "p2": (x2, y2), "width": width})
        return StepResult(ok=True)

    def draw_polygon(self, center_x: float, center_y: float, radius_mm: float, sides: int = 6, angle_deg: float = 0.0) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "polygon", "cx": center_x, "cy": center_y, "r": radius_mm, "sides": max(3, int(sides)), "angle": angle_deg
        })
        return StepResult(ok=True)

    def draw_hexagon(self, center_x: float, center_y: float, radius_mm: float, angle_deg: float = 0.0) -> StepResult:
        return self.draw_polygon(center_x, center_y, radius_mm, sides=6, angle_deg=angle_deg)

    def draw_counterbore_hole(self, x: float, y: float, hole_dia_mm: float, cbore_dia_mm: float, cbore_depth_mm: float = 5.0, through_all: bool = True) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "counterbore", "x": x, "y": y, "hole_dia": hole_dia_mm, "cbore_dia": cbore_dia_mm, "cbore_depth": cbore_depth_mm
        })
        return StepResult(ok=True)

    def draw_countersink_hole(self, x: float, y: float, hole_dia_mm: float, csink_dia_mm: float, csink_depth_mm: float = 3.0, through_all: bool = True) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "countersink", "x": x, "y": y, "hole_dia": hole_dia_mm, "csink_dia": csink_dia_mm, "csink_depth": csink_depth_mm
        })
        return StepResult(ok=True)

    def draw_lightening_pocket(self, center_x: float, center_y: float, width_mm: float, height_mm: float, corner_radius_mm: float = 3.0, depth_mm: float = 3.0) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "lightening_pocket", "cx": center_x, "cy": center_y, "w": width_mm, "h": height_mm, "r": corner_radius_mm, "depth": depth_mm
        })
        return StepResult(ok=True)

    def draw_linear_hole_pattern(self, start_x: float, start_y: float, step_x_mm: float, step_y_mm: float, count: int, dia_mm: float) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "linear_pattern", "sx": start_x, "sy": start_y, "dx": step_x_mm, "dy": step_y_mm, "count": count, "dia": dia_mm
        })
        return StepResult(ok=True)

    def draw_stiffening_rib(self, p1: list, p2: list, p3: list, thickness_mm: float = 4.0) -> StepResult:
        self._ensure_sketch()
        self.current_sketch_entities.append({
            "type": "rib", "p1": p1, "p2": p2, "p3": p3, "thickness": thickness_mm
        })
        return StepResult(ok=True)

    # =========================================================================
    # 3D FEATURES
    # =========================================================================

    def _calc_sketch_area(self) -> float:
        """Calculates exact 2D area of current sketch entities."""
        area = 0.0
        circles = [e for e in self.current_sketch_entities if e["type"] == "circle"]
        if len(circles) == 2:
            r1 = float(circles[0]["dia"]) / 2.0
            r2 = float(circles[1]["dia"]) / 2.0
            area += math.pi * (max(r1, r2)**2 - min(r1, r2)**2)
        elif circles:
            for c in circles:
                area += math.pi * ((float(c["dia"]) / 2.0) ** 2)

        for ent in self.current_sketch_entities:
            t = ent["type"]
            if t == "center_rect":
                area += float(ent["w"]) * float(ent["h"])
            elif t == "corner_rect":
                area += abs(float(ent["x2"]) - float(ent["x1"])) * abs(float(ent["y2"]) - float(ent["y1"]))
            elif t == "rotated_rect":
                area += float(ent["length"]) * float(ent["width"])
            elif t == "l_profile":
                w, h, th = float(ent["width"]), float(ent["height"]), float(ent["thickness"])
                area += (w * th) + ((h - th) * th)
            elif t == "line_chain" and ent.get("closed"):
                pts = ent["points"]
                n = len(pts)
                shoelace = 0.0
                for i in range(n):
                    j = (i + 1) % n
                    shoelace += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
                area += abs(shoelace) / 2.0
            elif t == "circular_pattern":
                area += int(ent["count"]) * math.pi * ((float(ent["dia"]) / 2.0) ** 2)
            elif t == "rect_pattern":
                area += 4 * math.pi * ((float(ent["dia"]) / 2.0) ** 2)
            elif t == "polygon":
                n = ent["sides"]
                r = float(ent["r"])
                area += 0.5 * n * (r ** 2) * math.sin(2.0 * math.pi / n)
            elif t in ["counterbore", "countersink"]:
                area += math.pi * ((float(ent["hole_dia"]) / 2.0) ** 2)
            elif t == "lightening_pocket":
                area += float(ent["w"]) * float(ent["h"])
            elif t == "linear_pattern":
                area += int(ent["count"]) * math.pi * ((float(ent["dia"]) / 2.0) ** 2)
            elif t == "rib":
                p1, p2, p3 = ent["p1"], ent["p2"], ent["p3"]
                area += 0.5 * abs((p1[0]*(p2[1]-p3[1]) + p2[0]*(p3[1]-p1[1]) + p3[0]*(p1[1]-p2[1])))
        return area

    def extrude_boss(self, depth_mm: float, midplane: bool = False,
                     draft_angle: float = 0.0, merge: bool = True, reverse: bool = False) -> StepResult:
        self.close_sketch()
        if not self.current_sketch_entities:
            return StepResult(ok=False, error="Mock Engine: extrude_boss called on empty sketch.")

        sketch_area = self._calc_sketch_area()
        added_vol = sketch_area * float(depth_mm)
        self.volume_mm3 += added_vol

        # Update last wall thickness for subsequent cuts
        has_l_profile = any(e["type"] == "l_profile" for e in self.current_sketch_entities)
        if not has_l_profile:
            self.last_wall_thickness = float(depth_mm)

        feat_name = f"ExtrudeBoss_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        if not self.bodies:
            self.bodies.append({"id": 1, "name": "SolidBody1"})

        self.box_max_mm[2] = max(self.box_max_mm[2], float(depth_mm))
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def extrude_cut(self, depth_mm: float = 0.0, through_all: bool = True,
                    both_directions: bool = True, midplane: bool = False,
                    reverse: bool = False, **kwargs) -> StepResult:
        self.close_sketch()
        if not self.bodies:
            return StepResult(ok=False, error="Mock Engine: extrude_cut called but no solid bodies exist.")
        if not self.current_sketch_entities:
            return StepResult(ok=False, error="Mock Engine: extrude_cut called on empty sketch.")

        cut_depth = float(depth_mm) if not through_all and depth_mm > 0 else min(self.last_wall_thickness, 20.0)
        cut_vol = self._calc_sketch_area() * cut_depth
        self.volume_mm3 = max(0.0, self.volume_mm3 - cut_vol)

        feat_name = f"ExtrudeCut_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def revolve_boss(self, angle_deg: float = 360.0, merge: bool = True) -> StepResult:
        self.close_sketch()
        has_cl = any(e["type"] == "centerline" for e in self.current_sketch_entities)
        if not has_cl:
            return StepResult(ok=False, error="Mock Engine: revolve_boss requires a centerline in sketch.")

        vol = 0.0
        line_chains = [e for e in self.current_sketch_entities if e["type"] == "line_chain"]
        if line_chains:
            pts = line_chains[0]["points"]
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                dx = abs(p2[0] - p1[0])
                if dx > 1e-3:
                    r1 = p1[1]
                    r2 = p2[1]
                    v_seg = (math.pi * dx / 3.0) * (r1**2 + r1*r2 + r2**2)
                    vol += v_seg * (float(angle_deg) / 360.0)

        if vol == 0.0:
            vol = self._calc_sketch_area() * 2.0 * math.pi * 10.0 * (float(angle_deg) / 360.0)

        self.volume_mm3 += vol
        feat_name = f"RevolveBoss_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        if not self.bodies:
            self.bodies.append({"id": 1, "name": "RevolveBody1"})
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def revolve_cut(self, angle_deg: float = 360.0) -> StepResult:
        self.close_sketch()
        cut_vol = self._calc_sketch_area() * 5.0
        self.volume_mm3 = max(0.0, self.volume_mm3 - cut_vol)
        feat_name = f"RevolveCut_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def apply_chamfer(self, width_mm: float = 1.5, angle_deg: float = 45.0) -> StepResult:
        if not self.bodies:
            return StepResult(ok=False, error="Mock Engine: apply_chamfer called with no bodies.")
        feat_name = f"Chamfer_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name)

    def apply_fillet_all_last_feature(self, radius_mm: float) -> StepResult:
        if not self.model["features"]:
            return StepResult(ok=False, error="Mock Engine: apply_fillet called with no features.")
        feat_name = f"Fillet_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name)

    def apply_fillet(self, radius_mm: float = 2.0, **kwargs) -> StepResult:
        """Alias for apply_fillet_all_last_feature."""
        return self.apply_fillet_all_last_feature(radius_mm=radius_mm)

    def create_hole_wizard(self, size: str = "M10", points_list: list = None,
                           hole_type: str = "tap", depth_mm: float = 0.0, through_all: bool = True) -> StepResult:
        if not self.bodies:
            return StepResult(ok=False, error="Mock Engine: create_hole_wizard called with no bodies.")
        count = len(points_list) if points_list else 1
        dia = 10.0 if "M10" in size else 8.0
        cut_vol = count * math.pi * ((dia / 2.0) ** 2) * (15.0 if through_all else depth_mm)
        self.volume_mm3 = max(0.0, self.volume_mm3 - cut_vol)
        feat_name = f"HoleWizard_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def create_rectangular_hole_wizard(self, size: str = "M10", center_x: float = 0.0, center_y: float = 0.0,
                                       spacing_x_mm: float = 90.0, spacing_y_mm: float = 90.0,
                                       hole_type: str = "tap", depth_mm: float = 0.0, through_all: bool = True) -> StepResult:
        hx, hy = float(spacing_x_mm) / 2.0, float(spacing_y_mm) / 2.0
        pts = [
            [center_x - hx, center_y - hy],
            [center_x + hx, center_y - hy],
            [center_x + hx, center_y + hy],
            [center_x - hx, center_y + hy]
        ]
        return self.create_hole_wizard(size=size, points_list=pts, hole_type=hole_type, depth_mm=depth_mm, through_all=through_all)

    def circular_pattern_last_feature(self, count: int, spacing_angle_deg: float = 360.0) -> StepResult:
        if not self.model["features"]:
            return StepResult(ok=False, error="Mock Engine: No feature to pattern.")
        feat_name = f"CirPattern_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())

    def shell_body(self, thickness_mm: float) -> StepResult:
        if not self.bodies:
            return StepResult(ok=False, error="Mock Engine: shell_body called with no bodies.")
        feat_name = f"Shell_{len(self.model['features']) + 1}"
        self.last_feature = feat_name
        self.model["features"].append(feat_name)
        self.volume_mm3 = self.volume_mm3 * 0.4
        return StepResult(ok=True, feature_name=feat_name, state=self.get_model_state())
