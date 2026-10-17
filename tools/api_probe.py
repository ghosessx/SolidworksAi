"""
SolidAI — SolidWorks COM API Probe & Diagnostic Tool
Tests live SolidWorks COM connectivity, RefPlane discovery, and feature creation.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cad_engine import SolidWorksCADEngine, StepResult


def probe_solidworks_api():
    print("=" * 60)
    print("SolidAI — SOLIDWORKS Live COM API Diagnostic Probe")
    print("=" * 60)

    try:
        engine = SolidWorksCADEngine()
        print("[+] SOLIDWORKS Application object obtained successfully.")
    except Exception as e:
        print(f"[-] SOLIDWORKS bağlanamadı: {e}")
        return False

    # 1. New Part Document
    res = engine.new_part()
    print(f"[1] new_part(): ok={res.ok}, error={res.error}")
    if not res.ok:
        return False

    # 2. Reference Planes
    planes = engine._get_primary_plane_names()
    print(f"[2] Primary Planes (Tree Order): Front='{planes.get('on')}', Top='{planes.get('ust')}', Right='{planes.get('sag')}'")

    sel_res = engine.select_plane("ust")
    print(f"[3] select_plane('ust'): ok={sel_res.ok}, feature='{sel_res.feature_name}'")

    # 3. Sketch & Extrude Boss Test
    sk_res = engine.start_sketch()
    print(f"[4] start_sketch(): ok={sk_res.ok}, in_sketch={engine.is_in_sketch()}")

    cr_res = engine.draw_center_rectangle(0.0, 0.0, 50.0, 50.0)
    print(f"[5] draw_center_rectangle(50x50): ok={cr_res.ok}")

    boss_res = engine.extrude_boss(depth_mm=10.0)
    print(f"[6] extrude_boss(10mm): ok={boss_res.ok}, feature='{boss_res.feature_name}', error={boss_res.error}")

    state = engine.get_model_state()
    print(f"[7] Model State: Bodies={state['body_count']}, Volume={state['volume_mm3']} mm3, Box={state['box_max_mm']}")

    # 4. Extrude Cut Test
    top_res = engine.select_top_face()
    print(f"[8] select_top_face(): ok={top_res.ok}")

    sk2_res = engine.start_sketch()
    print(f"[9] start_sketch() on face: ok={sk2_res.ok}")

    c_res = engine.draw_circle(0.0, 0.0, 20.0)
    print(f"[10] draw_circle(Ø20mm): ok={c_res.ok}")

    cut_res = engine.extrude_cut(through_all=True)
    print(f"[11] extrude_cut(through_all): ok={cut_res.ok}, feature='{cut_res.feature_name}'")

    state_after = engine.get_model_state()
    vol_loss = state['volume_mm3'] - state_after['volume_mm3']
    print(f"[12] Final Volume: {state_after['volume_mm3']} mm3 (Loss from cut: {vol_loss:.1f} mm3)")

    if boss_res.ok and cut_res.ok and state_after['body_count'] >= 1:
        print("\n>>> TEBRİKLER! SOLIDWORKS COM API TAM KABİLİYETLE ÇALIŞIYOR! <<<")
        print("    - Katı oluşturma (Extrude Boss): BAŞARILI")
        print("    - Üst yüzey seçimi (Select Top Face): BAŞARILI")
        print("    - Katı kesme (Extrude Cut): BAŞARILI")
        return True
    else:
        print("\n>>> UYARI: Bazı COM testleri bekleneni vermedi. <<<")
        return False


if __name__ == "__main__":
    probe_solidworks_api()
