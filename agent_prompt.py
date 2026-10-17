"""
SolidAI Autonomous CAD Agent — System Prompt & Dynamic Few-Shot Retrieval
Enforces strict JSON output, truthful engineering reasoning, and verified single-loop sketches.
"""
from typing import List, Dict


AGENT_SYSTEM_PROMPT = """You are a Senior Mechanical Design Engineer and Parametric CAD (SOLIDWORKS) Automation Expert.
Your objective is to analyze the user's mechanical design requirements and generate a 100% syntactically and geometrically valid JSON CAD Action Plan executed by SolidWorksCADEngine.

STRICT RULE: Your output MUST BE ONLY AND EXCLUSIVELY A VALID RAW JSON OBJECT. Do NOT include markdown code fences (```json), commentary, or explanations outside the JSON!
ALL LENGTHS AND DIMENSIONS ARE IN MILLIMETERS (mm), ANGLES IN DEGREES (deg)!

CAD ENGINE OPERATIONS:
1. Plane and Face Selection:
   - select_plane: {"plane": "top" | "front" | "right" | "ust" | "on" | "sag"}
   - select_top_face: {} (Selects topmost planar face of the solid body)
   - select_face: {"where": "top" | "front" | "bottom" | "left" | "right" | "largest_planar"}
   - select_face_by_ray: {"x": float, "y": float, "z": float, "dx": float, "dy": float, "dz": float}
   - create_ref_plane: {"base_plane": "top" | "front" | "right" | "ust" | "on" | "sag", "distance_mm": float}
   - select_ref_plane: {}

2. 2D Sketch Primitives:
   - start_sketch: {} (MUST be called before any drawing commands)
   - close_sketch: {}
   - draw_l_profile: {"width_mm": float, "height_mm": float, "thickness_mm": float}
   - draw_circle: {"x": float, "y": float, "dia": float}
   - draw_center_rectangle: {"x": float, "y": float, "w": float, "h": float}
   - draw_corner_rectangle: {"x1": float, "y1": float, "x2": float, "y2": float}
   - draw_rotated_rectangle: {"center_x": float, "center_y": float, "length_mm": float, "width_mm": float, "angle_deg": float}
   - draw_slot: {"x1": float, "y1": float, "x2": float, "y2": float, "width": float}
   - draw_polygon: {"center_x": float, "center_y": float, "radius_mm": float, "sides": int, "angle_deg": 0.0}
   - draw_hexagon: {"center_x": float, "center_y": float, "radius_mm": float, "angle_deg": 0.0}
   - draw_lightening_pocket: {"center_x": float, "center_y": float, "width_mm": float, "height_mm": float, "corner_radius_mm": float, "depth_mm": float}
   - draw_linear_hole_pattern: {"start_x": float, "start_y": float, "step_x_mm": float, "step_y_mm": float, "count": int, "dia_mm": float}
   - draw_counterbore_hole: {"x": float, "y": float, "hole_dia_mm": float, "cbore_dia_mm": float, "cbore_depth_mm": float}
   - draw_countersink_hole: {"x": float, "y": float, "hole_dia_mm": float, "csink_dia_mm": float, "csink_depth_mm": float}
   - draw_stiffening_rib: {"p1": [x, y], "p2": [x, y], "p3": [x, y], "thickness_mm": float}
   - draw_line_chain: {"points_list": [[x1, y1], [x2, y2], ...], "close_loop": true}
   - draw_centerline: {"x1": float, "y1": float, "x2": float, "y2": float}
   - draw_circular_hole_pattern: {"center_x": float, "center_y": float, "pcd_mm": float, "count": int, "dia_mm": float, "start_angle_deg": 0.0}
   - draw_rectangular_hole_pattern: {"center_x": float, "center_y": float, "spacing_x_mm": float, "spacing_y_mm": float, "dia_mm": float}

3. 3D Features & Solid Operations:
   - extrude_boss: {"depth_mm": float, "midplane": bool}
   - extrude_cut: {"depth_mm": float, "through_all": bool, "both_directions": bool}
   - create_rectangular_hole_wizard: {"size": "M10", "center_x": 0.0, "center_y": 0.0, "spacing_x_mm": float, "spacing_y_mm": float, "hole_type": "tap" | "clearance"}
   - create_hole_wizard: {"size": "M10", "points_list": [[x1, y1], ...], "hole_type": "tap" | "clearance"}
   - revolve_boss: {"angle_deg": float}
   - revolve_cut: {"angle_deg": float}
   - apply_chamfer: {"width_mm": float, "angle_deg": 45.0}
   - apply_fillet: {"radius_mm": float}
   - circular_pattern_last_feature: {"count": int, "spacing_angle_deg": 360.0}
   - shell_body: {"thickness_mm": float}

ENGINEERING RULES & ROBUST CAD PRINCIPLES:
1. SEQUENTIAL ATOMIC FEATURE MODELING: NEVER draw overlapping, untrimmed, or self-intersecting contours in a single sketch. Model each feature sequentially: Select Plane/Face -> start_sketch -> draw primitive -> extrude_boss or extrude_cut -> Rebuild.
2. ROTATED AND ANGLED GEOMETRIES: When drawing angled arms (e.g. 45°, 60° on drone frames or brackets), NEVER attempt to rotate a corner rectangle manually. ALWAYS use draw_rotated_rectangle({"center_x": float, "center_y": float, "length_mm": float, "width_mm": float, "angle_deg": float}). If multiple angled arms intersect at the origin (e.g., Quadcopter X-frame or Hexacopter), extrude each arm in its own sketch! SOLIDWORKS automatically merges overlapping solid bosses into a single solid body.
3. FULL THROUGH-CUT INTEGRITY: For all through-holes, slots, and cutouts, ALWAYS set "through_all": true and "both_directions": true to prevent reversed normal cut failures.
4. ENGINEERING CREATIVITY & FUNCTIONAL MORPHOLOGY: Whatever functional geometry is requested (e.g., custom drone frame, motor mounts, robotic arm linkages, bearing brackets, heat sinks), design it step-by-step from first geometric principles. Never settle for static generic placeholders.
5. FASTENING & BOLT HOLES: For cylindrical flanges, use draw_circular_hole_pattern (PCD). For rectangular patterns, use draw_rectangular_hole_pattern or create_rectangular_hole_wizard.
6. WEIGHT REDUCTION & AESTHETICS: Use draw_lightening_pocket (pocketing), draw_hexagon (weight-saving pockets), draw_slot (strap/cable pass-throughs), and apply_chamfer / apply_fillet for edge finishing.
7. ENGINEERING REASONING (Chain-of-Thought): Prior to the 'adimlar' (or 'steps') array, include the 'muhendislik_dusuncesi' (or 'engineering_reasoning') object to record coordinate calculations, center-of-mass balance, and structural logic.
"""


ALL_FEW_SHOT_LIBRARY = {
    # 1. Prizma / Plaka
    "prism": [
        {"role": "user", "content": "bana 5x5 mm bir kare çiz"},
        {"role": "assistant", "content": """{
  "parca_adi": "5x5 mm Kare Prizma",
  "tasarim_mantigi": "Üst düzlemde 5x5 mm merkez dikdörtgeni çiz ve 5 mm katıla.",
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 5.0, "h": 5.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 5.0}}
  ]
}"""}
    ],

    # 2. Boru Flanşı
    "flange": [
        {"role": "user", "content": "Bana 6 delikli standart bir boru flanşı çiz"},
        {"role": "assistant", "content": """{
  "parca_adi": "6 Delikli Boru Flanşı",
  "tasarim_mantigi": "140 mm disk katıla, merkez boru deliğini kes, üst yüze 6 cıvata deliği aç ve pah kır.",
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 140.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 15.0}},
    {"islem": "select_top_face", "params": {}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 50.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_top_face", "params": {}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circular_hole_pattern", "params": {"center_x": 0.0, "center_y": 0.0, "pcd_mm": 100.0, "count": 6, "dia_mm": 12.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "apply_chamfer", "params": {"width_mm": 1.5, "angle_deg": 45.0}}
  ]
}"""}
    ],

    # 3. Kademeli Mil
    "shaft": [
        {"role": "user", "content": "3 kademeli mil yap, uçlarına pah kır"},
        {"role": "assistant", "content": """{
  "parca_adi": "3 Kademeli Mil",
  "tasarim_mantigi": "Ön düzlemde dönme eksenini ve kademeli mil yarıçap konturunu çizip 360 derece döndür.",
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_centerline", "params": {"x1": 0.0, "y1": 0.0, "x2": 110.0, "y2": 0.0}},
    {"islem": "draw_line_chain", "params": {"points_list": [
      [0.0, 0.0], [0.0, 10.0], [30.0, 10.0], [30.0, 15.0], [70.0, 15.0], [70.0, 8.0], [110.0, 8.0], [110.0, 0.0]
    ], "close_loop": true}},
    {"islem": "revolve_boss", "params": {"angle_deg": 360.0}},
    {"islem": "apply_chamfer", "params": {"width_mm": 1.0, "angle_deg": 45.0}}
  ]
}"""}
    ],

    # 4. L-Braket / Motor Braketi
    "l_bracket": [
        {"role": "user", "content": "Bana bir NEMA 17 step motoru için L şeklinde montaj braketi tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "NEMA 17 Step Motor L-Montaj Braketi",
  "tasarim_mantigi": "Ön düzlemde 50x50x4 L-profil katıla, dikey yüze NEMA 17 delikleri ve tabana şase delikleri aç.",
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_l_profile", "params": {"width_mm": 50.0, "height_mm": 50.0, "thickness_mm": 4.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 45.0}},
    {"islem": "select_face", "params": {"where": "left"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 22.0}},
    {"islem": "draw_rectangular_hole_pattern", "params": {"center_x": 0.0, "center_y": 0.0, "spacing_x_mm": 31.0, "spacing_y_mm": 31.0, "dia_mm": 3.5}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_face", "params": {"where": "bottom"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -12.0, "y": 0.0, "dia": 5.0}},
    {"islem": "draw_circle", "params": {"x": 12.0, "y": 0.0, "dia": 5.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "apply_chamfer", "params": {"width_mm": 1.0, "angle_deg": 45.0}}
  ]
}"""}
    ],

    # 5. Yataklama Braketi (Pillow Block)
    "pillow_block": [
        {"role": "user", "content": "Tabanında kanal olan, silindirik gövdeli yataklama braketi (pillow block) tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "Yataklama Braketi (Pillow Block)",
  "tasarim_mantigi": "Taban kanalı ve gövdeyi katıla, rulman silindiri ve deliğini aç, federi ve montaj deliklerini oluştur.",
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_line_chain", "params": {"points_list": [
      [-70.0, 0.0], [-19.05, 0.0], [-19.05, 6.0], [19.05, 6.0], [19.05, 0.0], [70.0, 0.0], [70.0, 19.0], [-70.0, 19.0]
    ], "close_loop": true}},
    {"islem": "extrude_boss", "params": {"depth_mm": 89.0}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_line_chain", "params": {"points_list": [
      [-70.0, 19.0], [70.0, 19.0], [33.5, 120.0], [-33.5, 120.0]
    ], "close_loop": true}},
    {"islem": "extrude_boss", "params": {"depth_mm": 19.0}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 113.0, "dia": 70.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 45.0}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 113.0, "dia": 38.10}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "sag"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_line_chain", "params": {"points_list": [
      [-19.0, 19.0], [-89.0, 19.0], [-19.0, 80.0]
    ], "close_loop": true}},
    {"islem": "extrude_boss", "params": {"depth_mm": 19.0, "midplane": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -41.0, "y": -51.0, "dia": 19.0}},
    {"islem": "draw_circle", "params": {"x": 41.0, "y": -51.0, "dia": 19.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}}
  ]
}"""}
    ],

    # 6. Quadcopter X-Frame Şase Plakası (Sıralı Ayrı Çizim Modeli)
    "drone": [
        {"role": "user", "content": "Bana 240x16 mm çapraz kolları olan, 4 motor yuvalı, motor delikli ve FC montaj delikli bir quadcopter X-frame gövde plakası tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "Quadcopter X-Frame Şase Plakası",
  "tasarim_mantigi": "Merkez gövdeyi, 45 ve 135 derecelik açılı kolları ayrı çizimlerle katıla, motor yuvalarını ve montaj deliklerini oluştur.",
  "muhendislik_dusuncesi": {
    "fonksiyonel_analiz": "Quadcopter şasesi rijitlik ve hafiflik dengesi gerektirir. 4 motor kolu çapraz yerleşir.",
    "geometrik_yaklasim": "Merkez 70x70 mm plaka katılanacak, 45 ve 135 derece kollar ayrı sketch-extrude adımlarıyla eklenip birleştirilecek.",
    "yaraticilik_ve_hafifletme": "Merkez FC kulesi delikleri, motor şaft delikleri ve batarya yuvası slotları boydan boya kesilecek."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 70.0, "h": 70.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_rotated_rectangle", "params": {"center_x": 0.0, "center_y": 0.0, "length_mm": 240.0, "width_mm": 16.0, "angle_deg": 45.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_rotated_rectangle", "params": {"center_x": 0.0, "center_y": 0.0, "length_mm": 240.0, "width_mm": 16.0, "angle_deg": 135.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 84.85, "y": 84.85, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": -84.85, "y": 84.85, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": -84.85, "y": -84.85, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": 84.85, "y": -84.85, "dia": 28.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 16.0}},
    {"islem": "draw_rectangular_hole_pattern", "params": {"center_x": 0.0, "center_y": 0.0, "spacing_x_mm": 30.5, "spacing_y_mm": 30.5, "dia_mm": 3.0}},
    {"islem": "draw_circle", "params": {"x": 84.85, "y": 84.85, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": -84.85, "y": 84.85, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": -84.85, "y": -84.85, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": 84.85, "y": -84.85, "dia": 8.0}},
    {"islem": "draw_slot", "params": {"x1": -10.0, "y1": 24.0, "x2": 10.0, "y2": 24.0, "width": 3.2}},
    {"islem": "draw_slot", "params": {"x1": -10.0, "y1": -24.0, "x2": 10.0, "y2": -24.0, "width": 3.2}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}}
  ]
}"""}
    ],

    # 7. Hexacopter (6 Kollu Ağır Yük Drone Şasesi)
    "drone_hexacopter": [
        {"role": "user", "content": "Bana 6 kollu (hexacopter), ortasında petek hafifletmesi olan, 6 motor yuvalı profesyonel bir drone şasesi tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "6 Kollu Profesyonel Hexacopter Şasesi",
  "tasarim_mantigi": "Merkez altıgen gövdeyi katıla, 0, 60 ve 120 derecelik radyal kolları ekle, 6 motor yuvasını oluştur ve petek boşaltmasını kes.",
  "muhendislik_dusuncesi": {
    "fonksiyonel_analiz": "Hexacopter 6 pervaneli kaldırma kuvveti sağlar. 6 kol 60 derece simetriyle radyal dağılır.",
    "geometrik_yaklasim": "Merkez 45 mm altıgen gövde, 280x16 mm 3 adet çift-yönlü kol (0, 60, 120 derece) ile 6 kolun tamamı eksiksiz üretilir.",
    "yaraticilik_ve_hafifletme": "Merkezde 22 mm altıgen petek pencere, 6 uçta 8 mm motor şaft delikleri ve 140 mm yarıçaptaki motor montaj daireleri oluşturulur."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_hexagon", "params": {"center_x": 0.0, "center_y": 0.0, "radius_mm": 45.0, "angle_deg": 0.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_rotated_rectangle", "params": {"center_x": 0.0, "center_y": 0.0, "length_mm": 280.0, "width_mm": 16.0, "angle_deg": 0.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_rotated_rectangle", "params": {"center_x": 0.0, "center_y": 0.0, "length_mm": 280.0, "width_mm": 16.0, "angle_deg": 60.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_rotated_rectangle", "params": {"center_x": 0.0, "center_y": 0.0, "length_mm": 280.0, "width_mm": 16.0, "angle_deg": 120.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 140.0, "y": 0.0, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": -140.0, "y": 0.0, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": 70.0, "y": 121.24, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": -70.0, "y": -121.24, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": -70.0, "y": 121.24, "dia": 28.0}},
    {"islem": "draw_circle", "params": {"x": 70.0, "y": -121.24, "dia": 28.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_hexagon", "params": {"center_x": 0.0, "center_y": 0.0, "radius_mm": 22.0, "angle_deg": 0.0}},
    {"islem": "draw_circle", "params": {"x": 140.0, "y": 0.0, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": -140.0, "y": 0.0, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": 70.0, "y": 121.24, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": -70.0, "y": -121.24, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": -70.0, "y": 121.24, "dia": 8.0}},
    {"islem": "draw_circle", "params": {"x": 70.0, "y": -121.24, "dia": 8.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}}
  ]
}"""}
    ],

    # 8. Cinewhoop / Ducted Drone Şasesi (Pervane Koruma Halkalı)
    "drone_cinewhoop": [
        {"role": "user", "content": "Bana 4 pervanesinin etrafında dairesel koruma halkaları (ducts) olan bir cinewhoop drone şasesi tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "Cinewhoop Ducted Drone Şasesi",
  "tasarim_mantigi": "Merkez montaj gövdesini ve 4 dairesel pervane korumasını katıla, iç çapları boşaltarak rijit koruma kanalları oluştur.",
  "muhendislik_dusuncesi": {
    "fonksiyonel_analiz": "Cinewhoop iç mekan çekimleri için pervanelerin etrafında koruma halkaları (duct) taşır.",
    "geometrik_yaklasim": "Merkez 60x60 gövde, 4 köşede (x=±55, y=±55) 88 mm dış çaplı koruma diskleri katılanıp, 76 mm iç çapla boşaltılacak.",
    "yaraticilik_ve_hafifletme": "Merkez FC montaj delikleri ve batarya yarıkları boydan boya açılacak."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 60.0, "h": 60.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 55.0, "y": 55.0, "dia": 88.0}},
    {"islem": "draw_circle", "params": {"x": -55.0, "y": 55.0, "dia": 88.0}},
    {"islem": "draw_circle", "params": {"x": -55.0, "y": -55.0, "dia": 88.0}},
    {"islem": "draw_circle", "params": {"x": 55.0, "y": -55.0, "dia": 88.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 3.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 55.0, "y": 55.0, "dia": 76.0}},
    {"islem": "draw_circle", "params": {"x": -55.0, "y": 55.0, "dia": 76.0}},
    {"islem": "draw_circle", "params": {"x": -55.0, "y": -55.0, "dia": 76.0}},
    {"islem": "draw_circle", "params": {"x": 55.0, "y": -55.0, "dia": 76.0}},
    {"islem": "draw_rectangular_hole_pattern", "params": {"center_x": 0.0, "center_y": 0.0, "spacing_x_mm": 25.5, "spacing_y_mm": 25.5, "dia_mm": 2.5}},
    {"islem": "draw_slot", "params": {"x1": -8.0, "y1": 18.0, "x2": 8.0, "y2": 18.0, "width": 3.0}},
    {"islem": "draw_slot", "params": {"x1": -8.0, "y1": -18.0, "x2": 8.0, "y2": -18.0, "width": 3.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}}
  ]
}"""}
    ],

    # 9. Aerodinamik FPV Kamera Canopysi (Üst Koruma Podu)
    "drone_canopy": [
        {"role": "user", "content": "Bana FPV yarış dronu için aerodinamik kamera canopysi (üst koruma kabuğu) tasarla, kamera yuvası ve hava yarıkları olsun."},
        {"role": "assistant", "content": """{
  "parca_adi": "Aerodinamik FPV Kamera Canopysi",
  "tasarim_mantigi": "Montaj tabanını katıla, üstüne aerodinamik koruma kubbesini inşa et, kamera penceresi ve hava yarıklarını aç, pah kır.",
  "muhendislik_dusuncesi": {
    "fonksiyonel_analiz": "Canopy kamera ve elektronikleri darbelerden korurken hava akışı ve kamera açısı sağlamalıdır.",
    "geometrik_yaklasim": "Üst düzlemde 65x34 taban katılanır, üstüne 22 mm yüksekliğinde kubbe eklenir, ön tarafa kamera açısı slotu açılır.",
    "yaraticilik_ve_hafifletme": "Gövdeye 3 adet soğutma yarığı açılır ve aerodinamik yüzeyler için 1.5 mm pah uygulanır."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 65.0, "h": 34.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 2.5}},
    {"islem": "select_top_face", "params": {}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_slot", "params": {"x1": -12.0, "y1": 0.0, "x2": 12.0, "y2": 0.0, "width": 26.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 22.0}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 8.0, "y": 14.0, "dia": 14.0}},
    {"islem": "draw_slot", "params": {"x1": -10.0, "y1": 8.0, "x2": -10.0, "y2": 18.0, "width": 3.0}},
    {"islem": "draw_slot", "params": {"x1": -16.0, "y1": 8.0, "x2": -16.0, "y2": 18.0, "width": 3.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "apply_chamfer", "params": {"width_mm": 1.5, "angle_deg": 45.0}}
  ]
}"""}
    ],

    # 10. Yaratıcı ve Hafifletilmiş Robot Kolu Mafsalı (Aerospace / Robotics)
    "robot_joint": [
        {"role": "user", "content": "Bana yaratıcı, hafifletme cepleri ve montaj delikleri olan aerodinamik bir robot mafsal linki tasarla."},
        {"role": "assistant", "content": """{
  "parca_adi": "Hafifletilmiş Robot Kolu Mafsalı",
  "tasarim_mantigi": "Üst düzlemde 140x50 mm aerodinamik gövde ve mafsal kovanlarını katıla, petek hafifletme cepleri ve mil deliklerini aç, pah kır.",
  "muhendislik_dusuncesi": {
    "fonksiyonel_analiz": "Robot kolu eksenler arası moment iletimi sağlar, dönme merkezlerinde hassas mil yuvaları gerektirir.",
    "geometrik_yaklasim": "Üst düzlemde simetrik gövde katılanacak, iki uçta (x=-45, x=+45) 42 mm mafsal kovanları oluşturulacak.",
    "yaraticilik_ve_hafifletme": "Gövde ortasında ağırlığı azaltan 3 adet altıgen petek boşaltması açılacak, kenarlara 1.5 mm pah kırılarak gerilme dağıtılacak."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 90.0, "h": 36.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 20.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -45.0, "y": 0.0, "dia": 42.0}},
    {"islem": "draw_circle", "params": {"x": 45.0, "y": 0.0, "dia": 42.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 20.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -45.0, "y": 0.0, "dia": 20.0}},
    {"islem": "draw_circle", "params": {"x": 45.0, "y": 0.0, "dia": 20.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_hexagon", "params": {"center_x": 0.0, "center_y": 0.0, "radius_mm": 11.0, "angle_deg": 30.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_hexagon", "params": {"center_x": -22.0, "center_y": 0.0, "radius_mm": 8.0, "angle_deg": 30.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_hexagon", "params": {"center_x": 22.0, "center_y": 0.0, "radius_mm": 8.0, "angle_deg": 30.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "apply_chamfer", "params": {"width_mm": 1.5, "angle_deg": 45.0}}
  ]
}"""}
    ]
}


def get_relevant_few_shots(prompt: str, max_count: int = 1) -> List[Dict[str, str]]:
    """Dynamically retrieves only the most relevant few-shot example to keep
    prompt token count low, eliminate context overflow, and prevent hallucinated dimensions.
    """
    p = prompt.lower()
    selected_category = "prism"

    if any(k in p for k in ["hexacopter", "6 kol", "6-kol", "alti kol", "altı kol", "hexa"]):
        selected_category = "drone_hexacopter"
    elif any(k in p for k in ["cinewhoop", "whoop", "duct", "koruma halka", "korumalı", "prop guard", "pervane koruma"]):
        selected_category = "drone_cinewhoop"
    elif any(k in p for k in ["canopy", "kanopi", "kamera yuva", "kabuk", "pod", "kamera koruma"]):
        selected_category = "drone_canopy"
    elif any(k in p for k in ["drone", "quadcopter", "x-frame", "sase", "şase", "kol", "açılı", "acili", "angled"]):
        selected_category = "drone"
    elif any(k in p for k in ["robot", "mafsal", "joint", "link", "hafifletme", "petek", "pocket", "cep", "aerospace"]):
        selected_category = "robot_joint"
    elif any(k in p for k in ["flanş", "flans", "flange", "pcd", "cıvata"]):
        selected_category = "flange"
    elif any(k in p for k in ["mil", "shaft", "revolve", "döndür", "kasnak"]):
        selected_category = "shaft"
    elif any(k in p for k in ["braket", "bracket", "nema", "motor", "l-"]):
        selected_category = "l_bracket"
    elif any(k in p for k in ["pillow", "yatak", "bearing", "rulman"]):
        selected_category = "pillow_block"

    return ALL_FEW_SHOT_LIBRARY.get(selected_category, ALL_FEW_SHOT_LIBRARY["prism"])


# Legacy export for backwards compatibility
AGENT_FEW_SHOT_EXAMPLES = []
for k in ALL_FEW_SHOT_LIBRARY.keys():
    AGENT_FEW_SHOT_EXAMPLES.extend(ALL_FEW_SHOT_LIBRARY[k])

