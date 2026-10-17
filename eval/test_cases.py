"""
SolidAI Evaluation Suite — Golden Benchmark Test Cases
Contains verified exact physical engineering metrics (volume, body count, bbox) for standard parts.
"""
from parametric_templates import (
    generate_flange_plan,
    generate_l_bracket_plan,
    generate_stepped_shaft_plan,
    generate_pillow_block_plan,
    generate_shift_fork_plan,
    generate_quadcopter_frame_plan
)

GOLDEN_TEST_CASES = [
    {
        "id": "CASE_1_PRISM",
        "name": "5x5x5 mm Küp / Prizma",
        "plan": {
            "parca_adi": "5x5x5 mm Küp",
            "tasarim_mantigi": "Üst düzlemde 5x5 mm kare çiz ve 5 mm katıla.",
            "adimlar": [
                {"islem": "select_plane", "params": {"plane": "ust"}},
                {"islem": "start_sketch", "params": {}},
                {"islem": "draw_center_rectangle", "params": {"x": 0.0, "y": 0.0, "w": 5.0, "h": 5.0}},
                {"islem": "extrude_boss", "params": {"depth_mm": 5.0}}
            ]
        },
        "expected_body_count": 1,
        "expected_min_volume": 120.0,
        "expected_max_volume": 130.0
    },
    {
        "id": "CASE_2_FLANGE",
        "name": "6 Delikli Standart Boru Flanşı",
        "plan": generate_flange_plan(
            outer_dia=140.0, thickness=15.0, bore_dia=50.0,
            pcd=100.0, hole_count=6, hole_dia=12.0, chamfer_mm=1.5
        ),
        "expected_body_count": 1,
        "expected_min_volume": 180000.0,
        "expected_max_volume": 200000.0
    },
    {
        "id": "CASE_3_L_BRACKET",
        "name": "NEMA 17 Step Motor L-Montaj Braketi",
        "plan": generate_l_bracket_plan(
            width_mm=50.0, height_mm=50.0, thickness_mm=4.0, depth_mm=45.0, nema_motor=True
        ),
        "expected_body_count": 1,
        "expected_min_volume": 13000.0,
        "expected_max_volume": 17500.0
    },
    {
        "id": "CASE_4_STEPPED_SHAFT",
        "name": "3 Kademeli Mil",
        "plan": generate_stepped_shaft_plan([
            {"len": 30.0, "dia": 20.0},
            {"len": 40.0, "dia": 30.0},
            {"len": 40.0, "dia": 16.0}
        ]),
        "expected_body_count": 1,
        "expected_min_volume": 44000.0,
        "expected_max_volume": 47500.0
    },
    {
        "id": "CASE_5_PILLOW_BLOCK",
        "name": "Yataklama Braketi (Pillow Block)",
        "plan": generate_pillow_block_plan(),
        "expected_body_count": 1,
        "expected_min_volume": 450000.0,
        "expected_max_volume": 650000.0
    },
    {
        "id": "CASE_6_SHIFT_FORK",
        "name": "Vites Çatalı ve Mafsal (Practice 36)",
        "plan": generate_shift_fork_plan(),
        "expected_body_count": 1,
        "expected_min_volume": 80000.0,
        "expected_max_volume": 120000.0
    },
    {
        "id": "CASE_7_QUADCOPTER_FRAME",
        "name": "Quadcopter 240 mm X-Frame Şase Plakası",
        "plan": generate_quadcopter_frame_plan(),
        "expected_body_count": 1,
        "expected_min_volume": 35000.0,
        "expected_max_volume": 55000.0
    }
]

FAILURE_INJECTION_CASES = [
    {
        "id": "FAIL_1_UNKNOWN_OPERATION",
        "name": "Bilinmeyen CAD İşlemi Enjeksiyonu",
        "plan": {
            "parca_adi": "Bozuk Plan",
            "adimlar": [{"islem": "make_magic_geometry", "params": {}}]
        },
        "should_fail_at": "schema"
    },
    {
        "id": "FAIL_2_EMPTY_SKETCH_EXTRUSION",
        "name": "Boş Çizim Katılama Enjeksiyonu",
        "plan": {
            "parca_adi": "Boş Çizim",
            "adimlar": [
                {"islem": "select_plane", "params": {"plane": "ust"}},
                {"islem": "start_sketch", "params": {}},
                {"islem": "extrude_boss", "params": {"depth_mm": 20.0}}
            ]
        },
        "should_fail_at": "simulator"
    },
    {
        "id": "FAIL_3_REVOLVE_WITHOUT_AXIS",
        "name": "Eksensiz Döndürme Enjeksiyonu",
        "plan": {
            "parca_adi": "Eksensiz Revolve",
            "adimlar": [
                {"islem": "select_plane", "params": {"plane": "on"}},
                {"islem": "start_sketch", "params": {}},
                {"islem": "draw_circle", "params": {"x": 20.0, "y": 20.0, "dia": 10.0}},
                {"islem": "revolve_boss", "params": {"angle_deg": 360.0}}
            ]
        },
        "should_fail_at": "simulator"
    }
]
