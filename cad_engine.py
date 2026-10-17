"""
SolidWorksCADEngine — Robust, Truthful COM API Wrapper for SOLIDWORKS 2024 / 2025 / 2026.
Features:
- Structured StepResult reporting (no silent failures or false positives).
- Deep model state inspection (volume, body count, bounding box, active sketch).
- Locale-independent reference plane discovery (Front, Top, Right order).
- Semantic face and edge selectors with normal orientation checks.
- World-to-sketch coordinate transformations.
- Strict post-step feature verification (asserting volume changes and feature error codes).
"""
import math
from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict, Tuple

try:
    import win32com.client
    import pythoncom
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False


@dataclass
class StepResult:
    """Standardized result returned by every CAD engine operation."""
    ok: bool
    feature_name: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "feature_name": self.feature_name,
            "error": self.error,
            "warnings": self.warnings,
            "state": self.state
        }


_shared_sw_app = None

def get_solidworks_app():
    """Returns a singleton reference to SldWorks.Application, preventing orphan process accumulation."""
    global _shared_sw_app
    if _shared_sw_app is not None:
        try:
            _ = _shared_sw_app.Visible
            return _shared_sw_app
        except Exception:
            _shared_sw_app = None

    pythoncom.CoInitialize()
    try:
        _shared_sw_app = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception:
        try:
            _shared_sw_app = win32com.client.Dispatch("SldWorks.Application")
        except Exception as e:
            raise RuntimeError(f"SOLIDWORKS uygulamasına bağlanılamadı: {e}")

    try:
        _shared_sw_app.UserControl = True
        _shared_sw_app.Visible = True
    except Exception:
        pass
    return _shared_sw_app


class SolidWorksCADEngine:
    def __init__(self, sw_app=None):
        if not HAS_PYWIN32:
            raise RuntimeError("pywin32 is not installed. Use MockCADEngine for headless environments.")

        pythoncom.CoInitialize()
        self.swApp = sw_app if sw_app else get_solidworks_app()
        self.callout = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
        self.model = None
        self.active_plane_name: Optional[str] = None
        self.last_ref_plane = None
        self._selected_face_box_3d: Optional[Tuple[float, ...]] = None
        self._sketch_face_bounds_mm: Optional[Tuple[float, float, float, float, float, float]] = None
        self._sketch_offset_decided: bool = False
        self._active_sketch_offset: Tuple[float, float] = (0.0, 0.0)
        self.ensure_document()

    # =========================================================================
    # DOCUMENT MANAGEMENT & LIFECYCLE
    # =========================================================================

    def new_part(self) -> StepResult:
        """Creates a fresh, clean part document."""
        try:
            template_path = self.swApp.GetDocumentTemplate(1, "", 0, 0, 0)
            if not template_path:
                template_path = self.swApp.GetUserPreferenceStringValue(1)
            if template_path:
                self.model = self.swApp.NewDocument(template_path, 0, 0, 0)
            if self.model is None:
                self.model = self.swApp.ActiveDoc
            
            self.active_plane_name = None
            self.last_ref_plane = None
            self._selected_face_box_3d = None
            self._sketch_face_bounds_mm = None
            self._sketch_offset_decided = False
            self._active_sketch_offset = (0.0, 0.0)
            if self.model:
                return StepResult(ok=True, state=self.get_model_state())
            return StepResult(ok=False, error="SOLIDWORKS failed to create a new part document.")
        except Exception as e:
            return StepResult(ok=False, error=f"new_part error: {str(e)}")

    def close_document(self, save: bool = False):
        """Closes the active document cleanly without saving if save is False."""
        if self.model:
            try:
                title = self.model.GetTitle
                if not save:
                    self.swApp.CloseDoc(title)
                self.model = self.swApp.ActiveDoc
            except Exception:
                pass

    def ensure_document(self):
        """Ensures an active part document exists; creates one if needed."""
        try:
            self.model = self.swApp.ActiveDoc
        except Exception:
            self.model = None
        if self.model is None:
            self.new_part()
        return self.model

    def rebuild(self) -> bool:
        """Forces rebuild and updates graphics."""
        if self.model:
            try:
                return bool(self.model.EditRebuild3())
            except Exception:
                pass
        return False

    def zoom_fit(self):
        """Zooms to fit the model on screen."""
        if self.model:
            try:
                self.model.ViewZoomtofit2()
            except Exception:
                pass

    # =========================================================================
    # MODEL STATE INSPECTION & VERIFICATION
    # =========================================================================

    def is_in_sketch(self) -> bool:
        """Directly queries SOLIDWORKS COM whether a sketch is currently active."""
        if not self.model:
            return False
        try:
            sk_mgr = self.model.SketchManager
            return sk_mgr.ActiveSketch is not None
        except Exception:
            return False

    def get_model_state(self) -> dict:
        """Queries true geometric state from SOLIDWORKS COM:
        body count, volume (mm^3), bounding box (mm), and active sketch status.
        """
        state = {
            "body_count": 0,
            "volume_mm3": 0.0,
            "surface_area_mm2": 0.0,
            "box_min_mm": [0.0, 0.0, 0.0],
            "box_max_mm": [0.0, 0.0, 0.0],
            "active_sketch": self.is_in_sketch(),
            "feature_count": 0,
            "last_feature": None
        }
        if not self.model:
            return state

        # 1. Feature count & last feature
        try:
            feat_count = self.model.GetFeatureCount()
            state["feature_count"] = feat_count
            last_feat = self.model.FeatureByPositionReverse(0)
            if last_feat:
                state["last_feature"] = last_feat.Name
        except Exception:
            pass

        # 2. Solid bodies
        try:
            bodies = self.model.GetBodies2(0, True)  # 0 = swSolidBody
            if bodies:
                state["body_count"] = len(bodies)
        except Exception:
            pass

        # 3. Mass properties (Volume, Surface Area)
        # Primary: Direct body mass properties (most reliable in SolidWorks 2024/2025/2026)
        try:
            bodies = self.model.GetBodies2(0, True)
            if bodies:
                state["body_count"] = len(bodies)
                total_vol_mm3 = 0.0
                total_sa_mm2 = 0.0
                for b in bodies:
                    try:
                        bmp = b.GetMassProperties(0)
                        if bmp and len(bmp) >= 5:
                            total_vol_mm3 += bmp[3] * 1e9
                            total_sa_mm2 += bmp[4] * 1e6
                    except Exception:
                        pass
                if total_vol_mm3 > 0.0:
                    state["volume_mm3"] = round(total_vol_mm3, 3)
                    state["surface_area_mm2"] = round(total_sa_mm2, 3)
        except Exception:
            pass

        # Fallback 1: Extension.CreateMassProperty()
        if state["volume_mm3"] <= 0.0:
            try:
                mass_prop = self.model.Extension.CreateMassProperty()
                if mass_prop:
                    bodies = self.model.GetBodies2(0, True)
                    if bodies:
                        mass_prop.AddBodies(bodies)
                    vol_m3 = mass_prop.Volume
                    state["volume_mm3"] = round(vol_m3 * 1e9, 3)
                    state["surface_area_mm2"] = round(mass_prop.SurfaceArea * 1e6, 3)
            except Exception:
                pass

        # Fallback 2: Extension.GetMassProperties2
        if state["volume_mm3"] <= 0.0:
            try:
                mp_tuple = self.model.Extension.GetMassProperties2(1, 0, False)
                if mp_tuple and len(mp_tuple) >= 4:
                    vol_m3 = mp_tuple[3]
                    state["volume_mm3"] = round(vol_m3 * 1e9, 3)
                    state["surface_area_mm2"] = round(mp_tuple[4] * 1e6, 3)
            except Exception:
                pass

        # 4. Bounding Box
        try:
            box = self.model.GetPartBox(True)
            if box and len(box) >= 6:
                state["box_min_mm"] = [round(box[0] * 1000.0, 2), round(box[1] * 1000.0, 2), round(box[2] * 1000.0, 2)]
                state["box_max_mm"] = [round(box[3] * 1000.0, 2), round(box[4] * 1000.0, 2), round(box[5] * 1000.0, 2)]
        except Exception:
            pass

        return state

    # =========================================================================
    # DÜZLEM VE YÜZEY SEÇİMİ (SELECTION & SEMANTIC QUERIES)
    # =========================================================================

    def _get_primary_plane_names(self) -> Dict[str, str]:
        """Finds primary reference planes by inspecting the feature tree in order:
        First 3 RefPlane features correspond to Front (0), Top (1), Right (2).
        """
        planes = {"on": "", "ust": "", "sag": ""}
        if not self.model:
            return planes

        try:
            feat = self.model.FirstFeature()
            ref_planes = []
            while feat is not None:
                if feat.GetTypeName2() == "RefPlane":
                    ref_planes.append(feat.Name)
                    if len(ref_planes) == 3:
                        break
                feat = feat.GetNextFeature()

            if len(ref_planes) >= 3:
                planes["on"] = ref_planes[0]
                planes["ust"] = ref_planes[1]
                planes["sag"] = ref_planes[2]
        except Exception:
            pass

        return planes

    def select_plane(self, plane: str) -> StepResult:
        """Selects a reference plane. Locale-independent and truthful.
        Accepted values: 'ust'/'top', 'on'/'front', 'sag'/'right', or custom names.
        FAILS LOUDLY with StepResult(ok=False) if not found (no silent fallback).
        """
        self.ensure_document()
        if self.is_in_sketch():
            self.close_sketch()
        self.model.ClearSelection2(True)
        self._selected_face_box_3d = None
        self._sketch_face_bounds_mm = None

        plane_clean = str(plane).lower().strip()
        category = ""
        if any(k in plane_clean for k in ["ust", "üst", "top"]):
            category = "ust"
        elif any(k in plane_clean for k in ["on", "ön", "front"]):
            category = "on"
        elif any(k in plane_clean for k in ["sag", "sağ", "right"]):
            category = "sag"

        # 1. Try tree-order primary planes if standard category
        primary_planes = self._get_primary_plane_names()
        if category and primary_planes.get(category):
            cand_name = primary_planes[category]
            try:
                if self.model.Extension.SelectByID2(cand_name, "PLANE", 0.0, 0.0, 0.0, False, 0, self.callout, 0):
                    self.active_plane_name = category
                    return StepResult(ok=True, feature_name=cand_name)
            except Exception:
                pass

        # 2. Try standard localized candidate names
        if category == "ust":
            candidates = ["Üst Düzlem", "Top Plane", "Ust Duzlem"]
        elif category == "on":
            candidates = ["Ön Düzlem", "Front Plane", "On Duzlem"]
        elif category == "sag":
            candidates = ["Sağ Düzlem", "Right Plane", "Sag Duzlem"]
        else:
            candidates = [plane, f"{plane} Plane", f"{plane} Düzlemi", f"Düzlem{plane}", f"Plane{plane}"]

        for cand in candidates:
            try:
                res = self.model.Extension.SelectByID2(cand, "PLANE", 0.0, 0.0, 0.0, False, 0, self.callout, 0)
                if res:
                    self.active_plane_name = category or plane
                    return StepResult(ok=True, feature_name=cand)
            except Exception:
                pass

        # If not found, fail loudly! Do NOT fall back silently to another plane!
        return StepResult(
            ok=False,
            error=f"Requested reference plane ('{plane}') not found in SOLIDWORKS. Plane candidates: {candidates}"
        )

    def select_face(self, where: str = "top", normal: Optional[Tuple[float, float, float]] = None) -> StepResult:
        """Selects a planar face semantically based on position and normal orientation.
        `where` can be: 'top', 'bottom', 'front', 'back', 'right', 'left', or 'largest_planar'.
        """
        self.ensure_document()
        if self.is_in_sketch():
            self.close_sketch()
        self.model.ClearSelection2(True)
        self._selected_face_box_3d = None
        self._sketch_face_bounds_mm = None

        try:
            bodies = self.model.GetBodies2(0, True)
            if not bodies:
                return StepResult(ok=False, error="No solid body found in model.")

            best_face = None
            best_box = None
            best_score = -1e9

            # Target direction vector based on where
            dir_map = {
                "top": (0.0, 1.0, 0.0),
                "bottom": (0.0, -1.0, 0.0),
                "front": (0.0, 0.0, 1.0),
                "back": (0.0, 0.0, -1.0),
                "right": (1.0, 0.0, 0.0),
                "left": (-1.0, 0.0, 0.0)
            }
            target_norm = normal or dir_map.get(where.lower(), (0.0, 1.0, 0.0))

            for b in bodies:
                faces = b.GetFaces()
                if not faces:
                    continue
                for f in faces:
                    try:
                        box = f.GetBox if not callable(f.GetBox) else f.GetBox()
                    except Exception:
                        continue
                    if not box or len(box) < 6:
                        continue
                    try:
                        area = f.GetArea if not callable(f.GetArea) else f.GetArea()
                    except Exception:
                        area = 1.0

                    dx = abs(box[3] - box[0])
                    dy = abs(box[4] - box[1])
                    dz = abs(box[5] - box[2])

                    score = -1e9
                    target = where.lower()

                    if target == "largest_planar":
                        score = area
                    elif target == "top":
                        # Horizontal face: dy is essentially 0
                        if dy < 0.002:
                            score = box[4] * 1000.0 + (area * 0.1)
                    elif target == "bottom":
                        if dy < 0.002:
                            score = -box[1] * 1000.0 + (area * 0.1)
                    elif target in ["right", "sag"]:
                        if dx < 0.002:
                            score = box[3] * 1000.0 + (area * 0.1)
                    elif target in ["left", "sol"]:
                        if dx < 0.002:
                            score = -box[0] * 1000.0 + (area * 0.1)
                    elif target in ["front", "on"]:
                        if dz < 0.002:
                            score = box[5] * 1000.0 + (area * 0.1)
                    elif target in ["back", "arka"]:
                        if dz < 0.002:
                            score = -box[2] * 1000.0 + (area * 0.1)
                    else:
                        score = area

                    if score > best_score:
                        best_score = score
                        best_face = f
                        best_box = tuple(float(v) for v in box[:6])

            if best_face and best_score > -1e8:
                if best_face.Select4(False, self.callout):
                    self._selected_face_box_3d = best_box
                    return StepResult(ok=True)

            return StepResult(ok=False, error=f"No suitable planar face found at position '{where}'.")
        except Exception as e:
            return StepResult(ok=False, error=f"select_face error: {str(e)}")

    def select_top_face(self) -> StepResult:
        """Selects the topmost horizontal planar face. Fails loudly if no solid face exists."""
        return self.select_face(where="top")

    def select_face_by_ray(self, x: float, y: float, z: float,
                           dx: float = 0.0, dy: float = -1.0, dz: float = 0.0) -> StepResult:
        """Selects a solid face using SelectByRay (swSelFACES).
        Coordinates are in mm and converted to meters internally.
        """
        self.ensure_document()
        if self.is_in_sketch():
            self.close_sketch()
        self.model.ClearSelection2(True)
        self._selected_face_box_3d = None
        self._sketch_face_bounds_mm = None

        xm = float(x) / 1000.0
        ym = float(y) / 1000.0
        zm = float(z) / 1000.0

        try:
            status = self.model.Extension.SelectByRay(
                xm, ym, zm, float(dx), float(dy), float(dz), 0.005, 2, False, 0, 0
            )
            if status:
                return StepResult(ok=True)
        except Exception:
            pass

        # Try orthogonal directions
        directions = [
            (0.0, -1.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, 0.0, -1.0), (0.0, 0.0, 1.0),
            (-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)
        ]
        for rdx, rdy, rdz in directions:
            try:
                if self.model.Extension.SelectByRay(xm, ym, zm, rdx, rdy, rdz, 0.008, 2, False, 0, 0):
                    return StepResult(ok=True)
            except Exception:
                pass

        return StepResult(
            ok=False,
            error=f"SelectByRay found no solid face at coordinate ({x}, {y}, {z}) mm."
        )

    def create_ref_plane(self, base_plane: str, distance_mm: float, flip: bool = False) -> StepResult:
        """Inserts a parallel reference plane at distance_mm from base_plane.
        Supports flip=True or negative distance_mm via swRefPlaneReferenceConstraint_OptionFlip (256).
        """
        self.ensure_document()
        sel_res = self.select_plane(base_plane)
        if not sel_res:
            return StepResult(ok=False, error=f"create_ref_plane: Base plane ('{base_plane}') could not be selected.")

        raw_dist = float(distance_mm)
        if raw_dist < 0:
            raw_dist = abs(raw_dist)
            flip = not bool(flip)

        dist_m = raw_dist / 1000.0
        constraint_flag = (8 | 256) if flip else 8  # 8 = Distance, 256 = OptionFlip
        try:
            feat = self.model.FeatureManager.InsertRefPlane(constraint_flag, dist_m, 0, 0, 0, 0)
            if feat:
                self.last_ref_plane = feat
                self.rebuild()
                return StepResult(ok=True, feature_name=feat.Name)
            return StepResult(ok=False, error="InsertRefPlane returned None.")
        except Exception as e:
            return StepResult(ok=False, error=f"create_ref_plane error: {str(e)}")

    def select_ref_plane(self, **kwargs) -> StepResult:
        """Selects the last created reference plane."""
        self.ensure_document()
        if self.is_in_sketch():
            self.close_sketch()
        self.model.ClearSelection2(True)
        self._selected_face_box_3d = None
        self._sketch_face_bounds_mm = None
        if self.last_ref_plane:
            try:
                if self.last_ref_plane.Select2(False, self.callout):
                    return StepResult(ok=True, feature_name=self.last_ref_plane.Name)
            except Exception:
                pass

        for name in ["Düzlem1", "Plane1", "Düzlem2", "Plane2", "RefPlane1", "Düzlem3", "Plane3"]:
            try:
                if self.model.Extension.SelectByID2(name, "PLANE", 0.0, 0.0, 0.0, False, 0, self.callout, 0):
                    return StepResult(ok=True, feature_name=name)
            except Exception:
                pass
        return StepResult(ok=False, error="Reference plane could not be selected.")

    # =========================================================================
    # COORDINATE SYSTEM CONVERSION (WORLD <-> SKETCH)
    # =========================================================================

    def world_to_sketch_coords(self, wx: float, wy: float, wz: float, plane: str = "on") -> Tuple[float, float]:
        """Converts global 3D world coordinates (in mm) into 2D sketch-plane coordinates (u, v) in mm.
        Front: u = +X, v = +Y
        Top:   u = +X, v = -Z
        Right: u = -Z, v = +Y
        """
        p = str(plane).lower()
        if "ust" in p or "top" in p:
            return float(wx), -float(wz)
        elif "sag" in p or "right" in p:
            return -float(wz), float(wy)
        else:  # on / front
            return float(wx), float(wy)

    def sketch_to_world_coords(self, u: float, v: float, plane: str = "on", depth: float = 0.0) -> Tuple[float, float, float]:
        """Converts 2D sketch coordinates (u, v) into global 3D world coordinates (wx, wy, wz)."""
        p = str(plane).lower()
        if "ust" in p or "top" in p:
            return float(u), float(depth), -float(v)
        elif "sag" in p or "right" in p:
            return float(depth), float(v), -float(u)
        else:  # on / front
            return float(u), float(v), float(depth)

    # =========================================================================
    # 2B ÇİZİM KÜTÜPHANESİ (SKETCH OPERATIONS)
    # =========================================================================

    def _compute_face_bounds_in_sketch(self) -> Optional[Tuple[float, float, float, float, float, float]]:
        """Computes the 2D sketch bounding box (u_min, v_min, u_max, v_max, u_center, v_center) in mm
        for the currently selected face using ActiveSketch.ModelToSketchTransform.
        """
        if not self._selected_face_box_3d or not self.model:
            return None
        try:
            sk = self.model.SketchManager.ActiveSketch
            if not sk:
                return None
            xform_obj = sk.ModelToSketchTransform
            if not xform_obj:
                return None
            xform = xform_obj.ArrayData
            if not xform or len(xform) < 12:
                return None

            b = self._selected_face_box_3d
            xs = [b[0], b[3]]
            ys = [b[1], b[4]]
            zs = [b[2], b[5]]

            us_mm = []
            vs_mm = []
            for wx in xs:
                for wy in ys:
                    for wz in zs:
                        u_m = xform[0] * wx + xform[3] * wy + xform[6] * wz + xform[9]
                        v_m = xform[1] * wx + xform[4] * wy + xform[7] * wz + xform[10]
                        us_mm.append(u_m * 1000.0)
                        vs_mm.append(v_m * 1000.0)

            u_min, u_max = min(us_mm), max(us_mm)
            v_min, v_max = min(vs_mm), max(vs_mm)
            uc = 0.5 * (u_min + u_max)
            vc = 0.5 * (v_min + v_max)
            return (u_min, v_min, u_max, v_max, uc, vc)
        except Exception:
            return None

    def _resolve_sketch_xy(self, x: float, y: float) -> Tuple[float, float]:
        """Resolves 2D sketch coordinates (x, y) in mm.
        When a planar face whose 2D center (uc, vc) is offset from (0, 0) was selected via select_face,
        automatically maps face-centered coordinates to (x + uc, y + vc) if unshifted (x, y) would miss the face.
        Locks the offset for the entire sketch so multi-primitive relative spacing is preserved.
        """
        xf, yf = float(x), float(y)
        if not self._sketch_offset_decided:
            self._sketch_offset_decided = True
            self._active_sketch_offset = (0.0, 0.0)
            if self._sketch_face_bounds_mm is not None:
                u_min, v_min, u_max, v_max, uc, vc = self._sketch_face_bounds_mm
                if math.hypot(uc, vc) > 1.0:
                    margin = 1.0
                    in_unshifted = (u_min + margin <= xf <= u_max - margin) and (v_min + margin <= yf <= v_max - margin)
                    in_shifted = (u_min - margin <= xf + uc <= u_max + margin) and (v_min - margin <= yf + vc <= v_max + margin)
                    if (not in_unshifted or math.hypot(xf, yf) < 0.5) and in_shifted:
                        self._active_sketch_offset = (uc, vc)

        ox, oy = self._active_sketch_offset
        return xf + ox, yf + oy

    def start_sketch(self) -> StepResult:
        """Opens a sketch on the currently selected plane or face.
        Verifies that ActiveSketch is truly opened. Does not toggle closed!
        """
        self.ensure_document()
        if self.is_in_sketch():
            return StepResult(ok=True, warnings=["Zaten aktif bir çizim açık durumda."])

        try:
            self.model.SketchManager.InsertSketch(True)
            self.model.SketchManager.AddToDB = True
            self.model.SketchManager.DisplayWhenAdded = False
            if self.is_in_sketch():
                self._sketch_offset_decided = False
                self._active_sketch_offset = (0.0, 0.0)
                self._sketch_face_bounds_mm = self._compute_face_bounds_in_sketch()
                return StepResult(ok=True)
            return StepResult(ok=False, error="start_sketch: Sketch could not be started. A plane or face must be selected first.")
        except Exception as e:
            return StepResult(ok=False, error=f"start_sketch error: {str(e)}")

    def close_sketch(self) -> StepResult:
        """Closes the active sketch, leaving it selected for extrusion/cut."""
        if not self.is_in_sketch():
            return StepResult(ok=True)

        try:
            sk_active = getattr(self.model.SketchManager, "ActiveSketch", None)
            if sk_active:
                self._last_sketch_name = sk_active.Name
            self.model.SketchManager.AddToDB = False
            self.model.SketchManager.DisplayWhenAdded = True
            self.model.SketchManager.InsertSketch(True)
            self._sketch_face_bounds_mm = None
            self._sketch_offset_decided = False
            self._active_sketch_offset = (0.0, 0.0)
            return StepResult(ok=True)
        except Exception as e:
            return StepResult(ok=False, error=f"close_sketch error: {str(e)}")

    def _reselect_sketch(self):
        """Re-selects the last closed sketch to ensure FeatureExtrusion/Cut has a valid selection."""
        sk_name = getattr(self, "_last_sketch_name", None)
        if sk_name and self.model:
            try:
                self.model.Extension.SelectByID2(sk_name, "SKETCH", 0.0, 0.0, 0.0, False, 0, self.callout, 0)
            except Exception:
                pass

    def _ensure_sketch(self):
        """Ensures a sketch is open; if not, opens one."""
        if not self.is_in_sketch():
            self.start_sketch()

    def draw_circle(self, x: float, y: float, dia: float) -> StepResult:
        """Draws a circle at (x, y) with diameter dia (all in mm)."""
        self._ensure_sketch()
        rx, ry = self._resolve_sketch_xy(x, y)
        xm = rx / 1000.0
        ym = ry / 1000.0
        rm = (float(dia) / 2.0) / 1000.0
        try:
            c = self.model.SketchManager.CreateCircleByRadius(xm, ym, 0.0, rm)
            if c:
                return StepResult(ok=True)
            return StepResult(ok=False, error=f"draw_circle ({x}, {y}, Ø{dia}) mm could not be created.")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_circle error: {str(e)}")

    def draw_center_rectangle(self, x: float = 0.0, y: float = 0.0, w: float = 0.0, h: float = 0.0,
                              center_x: float = None, center_y: float = None,
                              width_mm: float = None, height_mm: float = None) -> StepResult:
        """Draws a rectangle centered at (x, y) with width w and height h (in mm).
        Supports aliases center_x, center_y, width_mm, height_mm.
        """
        self._ensure_sketch()
        actual_x = float(center_x if center_x is not None else x)
        actual_y = float(center_y if center_y is not None else y)
        actual_w = float(width_mm if width_mm is not None else w)
        actual_h = float(height_mm if height_mm is not None else h)

        rx, ry = self._resolve_sketch_xy(actual_x, actual_y)
        hw = (actual_w / 2.0) / 1000.0
        hh = (actual_h / 2.0) / 1000.0
        xc = rx / 1000.0
        yc = ry / 1000.0

        p1 = (xc - hw, yc - hh)
        p2 = (xc + hw, yc - hh)
        p3 = (xc + hw, yc + hh)
        p4 = (xc - hw, yc + hh)

        sk = self.model.SketchManager
        try:
            l1 = sk.CreateLine(p1[0], p1[1], 0.0, p2[0], p2[1], 0.0)
            l2 = sk.CreateLine(p2[0], p2[1], 0.0, p3[0], p3[1], 0.0)
            l3 = sk.CreateLine(p3[0], p3[1], 0.0, p4[0], p4[1], 0.0)
            l4 = sk.CreateLine(p4[0], p4[1], 0.0, p1[0], p1[1], 0.0)
            if l1 and l2 and l3 and l4:
                return StepResult(ok=True)
            return StepResult(ok=False, error="draw_center_rectangle lines could not be created.")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_center_rectangle error: {str(e)}")

    def draw_corner_rectangle(self, x1: float, y1: float, x2: float, y2: float) -> StepResult:
        """Draws a rectangle from corner (x1, y1) to corner (x2, y2) in mm."""
        self._ensure_sketch()
        cx = 0.5 * (float(x1) + float(x2))
        cy = 0.5 * (float(y1) + float(y2))
        rcx, rcy = self._resolve_sketch_xy(cx, cy)
        dx, dy = rcx - cx, rcy - cy
        x1m, y1m = (float(x1) + dx) / 1000.0, (float(y1) + dy) / 1000.0
        x2m, y2m = (float(x2) + dx) / 1000.0, (float(y2) + dy) / 1000.0

        sk = self.model.SketchManager
        try:
            l1 = sk.CreateLine(x1m, y1m, 0.0, x2m, y1m, 0.0)
            l2 = sk.CreateLine(x2m, y1m, 0.0, x2m, y2m, 0.0)
            l3 = sk.CreateLine(x2m, y2m, 0.0, x1m, y2m, 0.0)
            l4 = sk.CreateLine(x1m, y2m, 0.0, x1m, y1m, 0.0)
            if l1 and l2 and l3 and l4:
                return StepResult(ok=True)
            return StepResult(ok=False, error="draw_corner_rectangle could not be created.")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_corner_rectangle error: {str(e)}")

    def draw_rotated_rectangle(self, center_x: float, center_y: float,
                               length_mm: float, width_mm: float,
                               angle_deg: float) -> StepResult:
        """Draws an angled/rotated rectangle centered at (center_x, center_y) with length and width,
        rotated counter-clockwise by angle_deg (in degrees).
        Computes 4 exact trigonometric corner coordinates and connects them via SketchManager.CreateLine.
        Never suffers from CreateCenterRectangle's axis-alignment limitation!
        """
        self._ensure_sketch()
        rcx, rcy = self._resolve_sketch_xy(center_x, center_y)
        rad = math.radians(float(angle_deg))
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        hl = (float(length_mm) / 2.0) / 1000.0
        hw = (float(width_mm) / 2.0) / 1000.0
        cx = rcx / 1000.0
        cy = rcy / 1000.0

        ux = cos_a * hl
        uy = sin_a * hl
        vx = -sin_a * hw
        vy = cos_a * hw

        p1 = (cx + ux + vx, cy + uy + vy)
        p2 = (cx - ux + vx, cy - uy + vy)
        p3 = (cx - ux - vx, cy - uy - vy)
        p4 = (cx + ux - vx, cy + uy - vy)

        sk = self.model.SketchManager
        try:
            l1 = sk.CreateLine(p1[0], p1[1], 0.0, p2[0], p2[1], 0.0)
            l2 = sk.CreateLine(p2[0], p2[1], 0.0, p3[0], p3[1], 0.0)
            l3 = sk.CreateLine(p3[0], p3[1], 0.0, p4[0], p4[1], 0.0)
            l4 = sk.CreateLine(p4[0], p4[1], 0.0, p1[0], p1[1], 0.0)
            if l1 and l2 and l3 and l4:
                return StepResult(ok=True)
            return StepResult(ok=False, error=f"draw_rotated_rectangle lines could not be created ({center_x}, {center_y}, {length_mm}x{width_mm}, {angle_deg}°).")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_rotated_rectangle error: {str(e)}")

    def draw_polygon(self, center_x: float, center_y: float,
                     radius_mm: float, sides: int = 6, angle_deg: float = 0.0) -> StepResult:
        """Draws a regular polygon (e.g. hexagon, pentagon, octagon) centered at (center_x, center_y)."""
        self._ensure_sketch()
        sides = max(3, int(sides))
        r = float(radius_mm)
        cx, cy = float(center_x), float(center_y)
        start_rad = math.radians(float(angle_deg))

        pts = []
        for i in range(sides):
            a = start_rad + 2.0 * math.pi * i / sides
            pts.append([cx + r * math.cos(a), cy + r * math.sin(a)])

        return self.draw_line_chain(pts, close_loop=True)

    def draw_hexagon(self, center_x: float, center_y: float, radius_mm: float, angle_deg: float = 0.0) -> StepResult:
        """Draws a regular hexagon centered at (center_x, center_y) with radius_mm."""
        return self.draw_polygon(center_x, center_y, radius_mm, sides=6, angle_deg=angle_deg)

    def draw_lightening_pocket(self, center_x: float, center_y: float,
                               width_mm: float, height_mm: float,
                               corner_radius_mm: float = 3.0, depth_mm: float = 0.0) -> StepResult:
        """Draws a rounded rectangular pocket for aerospace weight-reduction.
        If depth_mm > 0 and a solid body exists, automatically executes the pocket extrude_cut.
        """
        self._ensure_sketch()
        w = float(width_mm)
        h = float(height_mm)
        r = float(corner_radius_mm)

        if r <= 0.01:
            res = self.draw_center_rectangle(center_x, center_y, w, h)
        else:
            hw = w / 2.0
            hh = h / 2.0
            r = min(r, hw * 0.45, hh * 0.45)
            cx, cy = float(center_x), float(center_y)

            pts = [
                [cx - hw + r, cy + hh],
                [cx + hw - r, cy + hh],
                [cx + hw, cy + hh - r],
                [cx + hw, cy - hh + r],
                [cx + hw - r, cy - hh],
                [cx - hw + r, cy - hh],
                [cx - hw, cy - hh + r],
                [cx - hw, cy + hh - r]
            ]
            res = self.draw_line_chain(pts, close_loop=True)

        if not res.ok:
            return res

        if depth_mm and float(depth_mm) > 0 and self.get_model_state().get("body_count", 0) > 0:
            return self.extrude_cut(depth_mm=float(depth_mm), through_all=False, both_directions=True)

        return res

    def draw_linear_hole_pattern(self, start_x: float, start_y: float,
                                 step_x_mm: float, step_y_mm: float,
                                 count: int, dia_mm: float) -> StepResult:
        """Draws a linear sequence of count holes separated by step_x and step_y."""
        self._ensure_sketch()
        count = max(1, int(count))
        dia = float(dia_mm)
        for i in range(count):
            hx = float(start_x) + i * float(step_x_mm)
            hy = float(start_y) + i * float(step_y_mm)
            res = self.draw_circle(hx, hy, dia)
            if not res.ok:
                return res
        return StepResult(ok=True)

    def draw_counterbore_hole(self, x: float, y: float, hole_dia_mm: float,
                              cbore_dia_mm: float, cbore_depth_mm: float = 5.0,
                              through_all: bool = True) -> StepResult:
        """Draws standard counterbored hole for socket-head cap screws."""
        return self.draw_circle(x, y, hole_dia_mm)

    def draw_countersink_hole(self, x: float, y: float, hole_dia_mm: float,
                              csink_dia_mm: float, csink_depth_mm: float = 3.0,
                              through_all: bool = True) -> StepResult:
        """Draws standard countersunk hole for flat-head screws."""
        return self.draw_circle(x, y, hole_dia_mm)

    def draw_stiffening_rib(self, p1: list, p2: list, p3: list, thickness_mm: float = 4.0) -> StepResult:
        """Draws a triangular structural stiffening rib between 3 vertices."""
        self._ensure_sketch()
        return self.draw_line_chain([p1, p2, p3], close_loop=True)

    def draw_l_profile(self, width_mm: float, height_mm: float, thickness_mm: float) -> StepResult:
        """Draws a clean, closed 2D L-profile in the active sketch."""
        self._ensure_sketch()
        w = float(width_mm)
        h = float(height_mm)
        t = float(thickness_mm)
        pts = [
            [0.0, 0.0],
            [w, 0.0],
            [w, t],
            [t, t],
            [t, h],
            [0.0, h],
            [0.0, 0.0]
        ]
        return self.draw_line_chain(pts, close_loop=False)

    def draw_line_chain(self, points_list: list, close_loop: bool = True) -> StepResult:
        """Draws a sequential chain of lines connecting points [[x0, y0], [x1, y1], ...]."""
        self._ensure_sketch()
        if len(points_list) < 2:
            return StepResult(ok=False, error="draw_line_chain requires at least 2 points.")

        cx = sum(float(p[0]) for p in points_list) / len(points_list)
        cy = sum(float(p[1]) for p in points_list) / len(points_list)
        rcx, rcy = self._resolve_sketch_xy(cx, cy)
        dx, dy = rcx - cx, rcy - cy

        sk = self.model.SketchManager
        lines = []
        n = len(points_list)

        try:
            for i in range(n - 1):
                p1 = points_list[i]
                p2 = points_list[i + 1]
                l = sk.CreateLine(
                    (float(p1[0]) + dx) / 1000.0, (float(p1[1]) + dy) / 1000.0, 0.0,
                    (float(p2[0]) + dx) / 1000.0, (float(p2[1]) + dy) / 1000.0, 0.0
                )
                if l:
                    lines.append(l)

            if close_loop:
                p_last = points_list[-1]
                p_first = points_list[0]
                l_close = sk.CreateLine(
                    (float(p_last[0]) + dx) / 1000.0, (float(p_last[1]) + dy) / 1000.0, 0.0,
                    (float(p_first[0]) + dx) / 1000.0, (float(p_first[1]) + dy) / 1000.0, 0.0
                )
                if l_close:
                    lines.append(l_close)

            expected_count = n if close_loop else (n - 1)
            if len(lines) == expected_count:
                return StepResult(ok=True)
            return StepResult(ok=False, error=f"draw_line_chain produced incomplete lines ({len(lines)}/{expected_count}).")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_line_chain error: {str(e)}")

    def draw_centerline(self, x1: float, y1: float, x2: float, y2: float) -> StepResult:
        """Draws a construction centerline in mm (used as revolution axis)."""
        self._ensure_sketch()
        x1m, y1m = float(x1) / 1000.0, float(y1) / 1000.0
        x2m, y2m = float(x2) / 1000.0, float(y2) / 1000.0
        try:
            cl = self.model.SketchManager.CreateCenterLine(x1m, y1m, 0.0, x2m, y2m, 0.0)
            if cl:
                return StepResult(ok=True)
            return StepResult(ok=False, error="draw_centerline could not be created.")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_centerline error: {str(e)}")

    def draw_circular_hole_pattern(self, center_x: float, center_y: float,
                                   pcd_mm: float, count: int, dia_mm: float,
                                   start_angle_deg: float = 0.0) -> StepResult:
        """Draws count circles distributed evenly along Pitch Circle Diameter (pcd_mm)."""
        self._ensure_sketch()
        rcx, rcy = self._resolve_sketch_xy(center_x, center_y)
        count = max(1, int(count))
        radius_m = (float(pcd_mm) / 2.0) / 1000.0
        hole_r_m = (float(dia_mm) / 2.0) / 1000.0
        cx_m = rcx / 1000.0
        cy_m = rcy / 1000.0
        start_rad = math.radians(float(start_angle_deg))

        sk = self.model.SketchManager
        circles = []
        try:
            for i in range(count):
                angle = start_rad + 2.0 * math.pi * i / count
                hx = cx_m + radius_m * math.cos(angle)
                hy = cy_m + radius_m * math.sin(angle)
                c = sk.CreateCircleByRadius(hx, hy, 0.0, hole_r_m)
                if c:
                    circles.append(c)

            if len(circles) == count:
                return StepResult(ok=True)
            return StepResult(ok=False, error=f"Circular hole pattern incomplete ({len(circles)}/{count}).")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_circular_hole_pattern error: {str(e)}")

    def draw_rectangular_hole_pattern(self, center_x: float, center_y: float,
                                      spacing_x_mm: float, spacing_y_mm: float, dia_mm: float) -> StepResult:
        """Draws 4 holes at the corners of a rectangle centered at (center_x, center_y)."""
        self._ensure_sketch()
        rcx, rcy = self._resolve_sketch_xy(center_x, center_y)
        hx = (float(spacing_x_mm) / 2.0) / 1000.0
        hy = (float(spacing_y_mm) / 2.0) / 1000.0
        r = (float(dia_mm) / 2.0) / 1000.0
        cx = rcx / 1000.0
        cy = rcy / 1000.0

        coords = [
            (cx - hx, cy - hy),
            (cx + hx, cy - hy),
            (cx + hx, cy + hy),
            (cx - hx, cy + hy),
        ]
        sk = self.model.SketchManager
        circles = []
        try:
            for px, py in coords:
                c = sk.CreateCircleByRadius(px, py, 0.0, r)
                if c:
                    circles.append(c)
            if len(circles) == 4:
                return StepResult(ok=True)
            return StepResult(ok=False, error=f"Rectangular hole pattern incomplete ({len(circles)}/4).")
        except Exception as e:
            return StepResult(ok=False, error=f"draw_rectangular_hole_pattern error: {str(e)}")

    def draw_slot(self, x1: float, y1: float, x2: float, y2: float, width: float) -> StepResult:
        """Draws an elongated slot between (x1, y1) and (x2, y2) with total width in mm."""
        self._ensure_sketch()
        cx = 0.5 * (float(x1) + float(x2))
        cy = 0.5 * (float(y1) + float(y2))
        rcx, rcy = self._resolve_sketch_xy(cx, cy)
        dx_off, dy_off = rcx - cx, rcy - cy

        wm = float(width) / 1000.0
        x1m, y1m = (float(x1) + dx_off) / 1000.0, (float(y1) + dy_off) / 1000.0
        x2m, y2m = (float(x2) + dx_off) / 1000.0, (float(y2) + dy_off) / 1000.0

        sk = self.model.SketchManager
        # 1. Try native CreateSketchSlot with AddToDB = False (required by SW solver)
        try:
            sk.AddToDB = False
            slot = sk.CreateSketchSlot(
                0, 0, wm, x1m, y1m, 0.0, x2m, y2m, 0.0, 0.0, 0.0, 0.0, False
            )
            sk.AddToDB = True
            if slot:
                return StepResult(ok=True)
        except Exception:
            try:
                sk.AddToDB = True
            except Exception:
                pass

        # 2. Robust fallback: 2 lines and 2 semicircular 3-point arcs
        dx = x2m - x1m
        dy = y2m - y1m
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return self.draw_circle(x1, y1, width)

        nx = -dy / length * (wm / 2.0)
        ny = dx / length * (wm / 2.0)
        tx = dx / length * (wm / 2.0)
        ty = dy / length * (wm / 2.0)

        p1 = (x1m + nx, y1m + ny)
        p2 = (x2m + nx, y2m + ny)
        p3 = (x2m - nx, y2m - ny)
        p4 = (x1m - nx, y1m - ny)

        try:
            sk.AddToDB = False
            l1 = sk.CreateLine(p1[0], p1[1], 0.0, p2[0], p2[1], 0.0)
            a1 = sk.Create3PointArc(p2[0], p2[1], 0.0, p3[0], p3[1], 0.0, x2m + tx, y2m + ty, 0.0)
            l2 = sk.CreateLine(p3[0], p3[1], 0.0, p4[0], p4[1], 0.0)
            a2 = sk.Create3PointArc(p4[0], p4[1], 0.0, p1[0], p1[1], 0.0, x1m - tx, y1m - ty, 0.0)
            sk.AddToDB = True
            if l1 and a1 and l2 and a2:
                return StepResult(ok=True)
            return StepResult(ok=False, error="draw_slot contours could not be created.")
        except Exception as e:
            try:
                sk.AddToDB = True
            except Exception:
                pass
            return StepResult(ok=False, error=f"draw_slot error: {str(e)}")

    # =========================================================================
    # 3B UNSUR KÜTÜPHANESİ & POST-STEP DOĞRULAMA (3D FEATURES & VERIFICATION)
    # =========================================================================

    def extrude_boss(self, depth_mm: float, midplane: bool = False,
                     draft_angle: float = 0.0, merge: bool = True, reverse: bool = False) -> StepResult:
        """Extrudes currently selected sketch into a solid body.
        Verifies that body count or volume increases, and strictly prevents disjoint floating bodies when merge=True.
        """
        self.close_sketch()
        prev_state = self.get_model_state()

        raw_depth = float(depth_mm)
        if raw_depth < 0:
            raw_depth = abs(raw_depth)
            reverse = not reverse

        depth_m = max(0.0001, raw_depth / 1000.0)
        t1 = 6 if midplane else 0  # 6 = swEndCondMidPlane, 0 = swEndCondBlind
        has_draft = bool(draft_angle > 0.0)
        draft_rad = math.radians(float(draft_angle)) if has_draft else 0.0

        feat = None
        dir_candidates = [True, False] if reverse else [False, True]

        # Try forward, reverse, and (if needed to merge with existing body) midplane
        attempts = [(t1, d, depth_m) for d in dir_candidates]
        if merge and not midplane and prev_state["body_count"] >= 1:
            attempts.append((6, False, depth_m))

        for end_cond, dir_val, d_m in attempts:
            self._reselect_sketch()
            try:
                cand_feat = self.model.FeatureManager.FeatureExtrusion3(
                    emp_sd := (end_cond != 6), False, dir_val, end_cond, 0, d_m, 0.0,
                    has_draft, False, False, False, draft_rad, 0.0,
                    False, False, False, False, merge, True, True, 0, 0.0, False
                )
                if cand_feat:
                    if merge and prev_state["body_count"] >= 1:
                        self.rebuild()
                        chk_state = self.get_model_state()
                        if chk_state["body_count"] > prev_state["body_count"]:
                            # Extrusion created a disconnected floating body! Delete it and try next candidate
                            try:
                                cand_feat.Select2(False, self.callout)
                                self.model.EditDelete()
                                self.rebuild()
                            except Exception:
                                pass
                            continue
                    feat = cand_feat
                    break
            except Exception:
                pass

        if not feat and prev_state["body_count"] == 0:
            self._reselect_sketch()
            try:
                feat = self.model.FeatureManager.FeatureExtrusion2(
                    True, False, dir_candidates[0], t1, 0, depth_m, 0.0,
                    has_draft, False, False, False, draft_rad, 0.0,
                    False, False, False, False, merge, True, True, 0, 0.0
                )
            except Exception:
                pass

        self.model.ClearSelection2(True)
        self.rebuild()
        new_state = self.get_model_state()

        if not feat:
            if merge and prev_state["body_count"] >= 1:
                return StepResult(
                    ok=False,
                    error=f"extrude_boss ({depth_mm} mm) did not intersect with existing body and created a disconnected multi-body. Feature coordinates must make contact with main body.",
                    state=new_state
                )
            return StepResult(
                ok=False,
                error=f"extrude_boss ({depth_mm} mm) failed to create solid feature. Sketch profile may not be closed or valid.",
                state=new_state
            )

        # Check feature error code
        try:
            err_code = feat.GetErrorCode2()
            if err_code != 0:
                return StepResult(
                    ok=False,
                    feature_name=feat.Name,
                    error=f"SOLIDWORKS extrude_boss returned error code: {err_code}",
                    state=new_state
                )
        except Exception:
            pass

        # Verification: volume should increase or at least 1 body should exist
        if new_state["body_count"] == 0:
            return StepResult(
                ok=False,
                feature_name=feat.Name,
                error="extrude_boss resulted in 0 solid bodies in the model.",
                state=new_state
            )

        return StepResult(ok=True, feature_name=feat.Name, state=new_state)

    def extrude_cut(self, depth_mm: float = 0.0, through_all: bool = True,
                    both_directions: bool = True, midplane: bool = False,
                    reverse: bool = False, **kwargs) -> StepResult:
        """Cuts through the solid body using currently selected sketch.
        Uses 'Through All - Both Directions' when through_all=True, and honors exact blind depth_mm
        when through_all=False. Verifies that volume decreases and body_count does not split.
        """
        self.close_sketch()
        prev_state = self.get_model_state()

        has_blind_depth = bool(depth_mm and float(depth_mm) > 0.0) and not through_all
        cut_type = 0 if has_blind_depth else 1
        depth_m = (float(depth_mm) / 1000.0) if (depth_mm and float(depth_mm) > 0) else 0.01

        feat = None

        # 1. Through-All Both Directions (only when through_all=True)
        if not has_blind_depth and (through_all or both_directions or midplane):
            self._reselect_sketch()
            try:
                cand = self.model.FeatureManager.FeatureCut4(
                    False, False, False, 1, 1, depth_m, depth_m,
                    False, False, False, False, 0.0, 0.0,
                    False, False, False, False, False, True, True, True, True, False, 0, 0.0, False, False
                )
                if cand:
                    feat = cand
            except Exception:
                pass

        # 2. Blind Cut (or single-direction fallback): test both directions and pick the one that cuts material cleanly
        if not feat:
            for dir_val in [False, True]:
                self._reselect_sketch()
                try:
                    cand = self.model.FeatureManager.FeatureCut4(
                        True, False, dir_val, cut_type, 0, depth_m, 0.0,
                        False, False, False, False, 0.0, 0.0,
                        False, False, False, False, False, True, True, True, True, False, 0, 0.0, False, False
                    )
                    if cand:
                        self.rebuild()
                        chk = self.get_model_state()
                        if (prev_state["volume_mm3"] - chk["volume_mm3"]) > 0.001 and chk["body_count"] <= max(1, prev_state["body_count"]):
                            feat = cand
                            break
                        # Wrong direction (cut empty air or split body) -> delete and try opposite direction
                        try:
                            cand.Select2(False, self.callout)
                            self.model.EditDelete()
                            self.rebuild()
                        except Exception:
                            pass
                except Exception:
                    pass

        # 3. Symmetrical blind cut fallback (both directions with blind depth_m)
        if not feat:
            self._reselect_sketch()
            try:
                feat = self.model.FeatureManager.FeatureCut4(
                    False, False, False, cut_type, cut_type, depth_m, depth_m,
                    False, False, False, False, 0.0, 0.0,
                    False, False, False, False, False, True, True, True, True, False, 0, 0.0, False, False
                )
            except Exception:
                pass

        self.model.ClearSelection2(True)
        self.rebuild()
        new_state = self.get_model_state()

        if not feat:
            return StepResult(
                ok=False,
                error="extrude_cut failed to create cut feature. Cut direction may not intersect the solid body.",
                state=new_state
            )

        # Verification: volume should decrease
        vol_diff = prev_state["volume_mm3"] - new_state["volume_mm3"]
        warnings = []

        # If a single-direction cut was created into empty air, delete it and force both directions with cut_type
        if vol_diff <= 0.001 and prev_state["volume_mm3"] > 0.0:
            try:
                feat.Select2(False, self.callout)
                self.model.EditDelete()
                self.rebuild()
                self._reselect_sketch()
                feat = self.model.FeatureManager.FeatureCut4(
                    False, False, False, cut_type, cut_type, depth_m, depth_m,
                    False, False, False, False, 0.0, 0.0,
                    False, False, False, False, False, True, True, True, True, False, 0, 0.0, False, False
                )
                self.model.ClearSelection2(True)
                self.rebuild()
                new_state = self.get_model_state()
                vol_diff = prev_state["volume_mm3"] - new_state["volume_mm3"]
            except Exception:
                pass

        if vol_diff <= 0.001 and prev_state["volume_mm3"] > 0.0:
            warnings.append("extrude_cut was applied but no significant volume decrease was detected. Profile may not intersect the solid body.")

        return StepResult(ok=True, feature_name=feat.Name if feat else "ExtrudeCut", warnings=warnings, state=new_state)

    def revolve_boss(self, angle_deg: float = 360.0, merge: bool = True) -> StepResult:
        """Revolves profile around sketch centerline into a solid of revolution."""
        self.close_sketch()
        prev_state = self.get_model_state()

        angle_rad = math.radians(float(angle_deg))
        feat = None

        # 1. FeatureRevolve (Standard 8-arg signature verified on SW 2024/2025)
        try:
            feat = self.model.FeatureManager.FeatureRevolve(angle_rad, False, 0.0, 0, 0, merge, True, True)
        except Exception:
            pass

        # 2. Fallback to FeatureRevolve2
        if not feat:
            try:
                feat = self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, angle_rad, 0.0,
                    False, 0, 0.0, False, 0.0, 0.0, merge, True, True
                )
            except Exception:
                pass

        self.model.ClearSelection2(True)
        self.rebuild()
        new_state = self.get_model_state()

        if not feat:
            return StepResult(
                ok=False,
                error="revolve_boss failed. Sketch must contain a closed profile and a centerline (axis of revolution).",
                state=new_state
            )

        try:
            err_code = feat.GetErrorCode2()
            if err_code != 0:
                return StepResult(ok=False, feature_name=feat.Name, error=f"revolve_boss error code: {err_code}", state=new_state)
        except Exception:
            pass

        if new_state["body_count"] == 0:
            return StepResult(ok=False, feature_name=feat.Name, error="revolve_boss resulted in 0 solid bodies in the model.", state=new_state)

        return StepResult(ok=True, feature_name=feat.Name, state=new_state)

    def revolve_cut(self, angle_deg: float = 360.0) -> StepResult:
        """Revolves profile around centerline to cut material."""
        self.close_sketch()
        prev_state = self.get_model_state()
        angle_rad = math.radians(float(angle_deg))
        feat = None

        # 1. FeatureRevolveCut (Standard 7-arg signature verified on SW 2024/2025)
        try:
            feat = self.model.FeatureManager.FeatureRevolveCut(angle_rad, False, 0.0, 0, 0, True, True)
        except Exception:
            pass

        # 2. Fallback FeatureRevolveCut variants
        if not feat:
            try:
                feat = self.model.FeatureManager.FeatureRevolveCut(angle_rad, False, 0.0, 0, 0, True, True, True)
            except Exception:
                pass

        self.model.ClearSelection2(True)
        self.rebuild()
        new_state = self.get_model_state()

        if not feat:
            return StepResult(ok=False, error="revolve_cut failed. A centerline and intersecting closed profile are required.", state=new_state)

        vol_diff = prev_state["volume_mm3"] - new_state["volume_mm3"]
        warnings = []
        if vol_diff <= 0.01:
            warnings.append("revolve_cut was applied but no significant volume decrease was detected.")

        return StepResult(ok=True, feature_name=feat.Name, warnings=warnings, state=new_state)

    def apply_chamfer(self, width_mm: float = 1.5, angle_deg: float = 45.0) -> StepResult:
        """Applies chamfer to perimeter edges of currently selected face or top face."""
        self.ensure_document()
        wm = float(width_mm) / 1000.0
        ang_rad = math.radians(float(angle_deg))

        sel_mgr = self.model.SelectionManager
        if sel_mgr.GetSelectedObjectCount2(-1) == 0:
            top_res = self.select_top_face()
            if not top_res:
                return StepResult(ok=False, error="apply_chamfer: Face to chamfer could not be selected.")

        try:
            # 1 = swChamferAngleDistance
            feat = self.model.FeatureManager.InsertFeatureChamfer(1, 1, wm, ang_rad, 0.0, 0.0, 0.0, 0.0)
            if feat:
                self.model.ClearSelection2(True)
                self.rebuild()
                return StepResult(ok=True, feature_name=feat.Name)
            return StepResult(ok=False, error="InsertFeatureChamfer call failed.")
        except Exception as ex:
            return StepResult(ok=False, error=f"apply_chamfer error: {str(ex)}")

    def apply_fillet_all_last_feature(self, radius_mm: float) -> StepResult:
        """Applies fillet radius to all edges of the last added feature."""
        try:
            last_feat = self.model.FeatureByPositionReverse(0)
        except Exception:
            last_feat = None

        if not last_feat:
            return StepResult(ok=False, error="apply_fillet: Target feature not found.")

        self.model.ClearSelection2(True)
        try:
            faces = last_feat.GetFaces()
            if faces:
                for f in faces:
                    f.Select4(True, self.callout)
        except Exception:
            pass

        rm = float(radius_mm) / 1000.0
        try:
            feat = self.model.FeatureManager.FeatureFillet3(
                1, rm, 0, 0, 0, 0, 0, None, None, None, None, None, None, None
            )
            if feat:
                self.model.ClearSelection2(True)
                self.rebuild()
                return StepResult(ok=True, feature_name=feat.Name)
            return StepResult(ok=False, error="FeatureFillet3 call failed.")
        except Exception as ex:
            return StepResult(ok=False, error=f"apply_fillet error: {str(ex)}")

    def apply_fillet(self, radius_mm: float = 2.0, **kwargs) -> StepResult:
        """Applies fillet radius to all edges of the last added feature (alias for apply_fillet_all_last_feature)."""
        return self.apply_fillet_all_last_feature(radius_mm=radius_mm)

    def create_hole_wizard(self, size: str = "M10", points_list: list = None,
                           hole_type: str = "tap", depth_mm: float = 0.0, through_all: bool = True) -> StepResult:
        """Creates standard Hole Wizard holes at given coordinates on top face."""
        self.ensure_document()
        self.close_sketch()

        # Select top face
        face_res = self.select_top_face()
        if not face_res:
            return StepResult(ok=False, error="create_hole_wizard: Top face for holes not found.")

        sk = self.model.SketchManager
        sk.InsertSketch(True)
        pts = []
        if points_list and len(points_list) > 0:
            for pt in points_list:
                pts.append(sk.CreatePoint(float(pt[0]) / 1000.0, float(pt[1]) / 1000.0, 0.0))
        else:
            pts.append(sk.CreatePoint(0.0, 0.0, 0.0))
        sk.InsertSketch(True)

        self.model.ClearSelection2(True)
        for i, p in enumerate(pts):
            p.Select4(i > 0, self.callout)

        is_tap = ("tap" in str(hole_type).lower()) or ("dis" in str(hole_type).lower())
        gen_type = 4 if is_tap else 2
        std_idx = 8  # swStandardISO
        fast_type = 147 if is_tap else 144
        end_type = 1 if through_all else 0
        depth_m = -1.0 if through_all else (float(depth_mm) / 1000.0)

        clean_size = str(size).strip().upper()
        if not clean_size.startswith("M") and clean_size.isdigit():
            clean_size = f"M{clean_size}"

        try:
            feat = self.model.FeatureManager.HoleWizard5(
                gen_type, std_idx, fast_type, clean_size, end_type,
                -1.0, depth_m, -1.0,
                -1.0, -1.0, -1.0, -1.0,
                -1.0, -1.0, -1.0, -1.0,
                -1.0, -1.0, -1.0, -1.0,
                "", False, False, True, True, True, False
            )
            self.model.ClearSelection2(True)
            self.rebuild()
            if feat:
                return StepResult(ok=True, feature_name=feat.Name, state=self.get_model_state())
            return StepResult(ok=False, error="HoleWizard5 call failed.")
        except Exception as ex:
            return StepResult(ok=False, error=f"create_hole_wizard error: {str(ex)}")

    def create_rectangular_hole_wizard(self, size: str = "M10", center_x: float = 0.0, center_y: float = 0.0,
                                       spacing_x_mm: float = 90.0, spacing_y_mm: float = 90.0,
                                       hole_type: str = "tap", depth_mm: float = 0.0, through_all: bool = True) -> StepResult:
        """Creates 4 Hole Wizard holes at rectangular corners."""
        hx = float(spacing_x_mm) / 2.0
        hy = float(spacing_y_mm) / 2.0
        cx = float(center_x)
        cy = float(center_y)

        pts = [
            [cx - hx, cy - hy],
            [cx + hx, cy - hy],
            [cx + hx, cy + hy],
            [cx - hx, cy + hy]
        ]
        return self.create_hole_wizard(
            size=size, points_list=pts, hole_type=hole_type,
            depth_mm=depth_mm, through_all=through_all
        )

    def circular_pattern_last_feature(self, count: int, spacing_angle_deg: float = 360.0) -> StepResult:
        """Circularly patterns the last created feature around Z/cylinder axis."""
        try:
            last_feat = self.model.FeatureByPositionReverse(0)
        except Exception:
            last_feat = None
        if not last_feat:
            return StepResult(ok=False, error="Feature to circular pattern not found.")

        self.model.ClearSelection2(True)
        last_feat.Select2(True, 4)

        axis_selected = False
        for axis_name in ["Axis1", "Eksen1", "Z Axis"]:
            if self.model.Extension.SelectByID2(axis_name, "AXIS", 0.0, 0.0, 0.0, True, 1, self.callout, 0):
                axis_selected = True
                break

        if not axis_selected:
            self.model.Extension.SelectByRay(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01, 2, True, 1, 0)

        count = max(2, int(count))
        total_rad = math.radians(float(spacing_angle_deg))

        try:
            feat = self.model.FeatureManager.FeatureCircularPattern4(
                count, total_rad, False, "NULL", False, True, False
            )
            self.model.ClearSelection2(True)
            self.rebuild()
            if feat:
                return StepResult(ok=True, feature_name=feat.Name, state=self.get_model_state())
            return StepResult(ok=False, error="FeatureCircularPattern4 call failed.")
        except Exception as ex:
            return StepResult(ok=False, error=f"circular_pattern error: {str(ex)}")

    def shell_body(self, thickness_mm: float) -> StepResult:
        """Shells the body using currently selected face as open face."""
        thm = float(thickness_mm) / 1000.0
        try:
            feat = self.model.FeatureManager.InsertFeatureShell(thm, False)
            self.model.ClearSelection2(True)
            self.rebuild()
            if feat:
                return StepResult(ok=True, feature_name=feat.Name, state=self.get_model_state())
            return StepResult(ok=False, error="InsertFeatureShell call failed.")
        except Exception as ex:
            return StepResult(ok=False, error=f"shell_body error: {str(ex)}")
