"""
Diagnostic to test Face2 properties on live SolidWorks.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cad_engine import SolidWorksCADEngine

engine = SolidWorksCADEngine()
print("1. Creating new part...")
engine.new_part()

print("2. Selecting plane 'ust'...")
engine.select_plane("ust")

print("3. Starting sketch & extruding...")
engine.start_sketch()
engine.draw_center_rectangle(0.0, 0.0, 50.0, 50.0)
boss_res = engine.extrude_boss(depth_mm=10.0)
print(f"extrude_boss: ok={boss_res.ok}, feat={boss_res.feature_name}")

print("4. Testing Face2 properties directly...")
bodies = engine.model.GetBodies2(0, True)
print(f"bodies: {len(bodies) if bodies else 0}")
best_face = None
best_y = -1e9

for b in bodies:
    faces = b.GetFaces()
    print(f"body faces: {len(faces) if faces else 0}")
    for fi, f in enumerate(faces):
        # Handle win32com property vs method
        box = f.GetBox if not callable(f.GetBox) else f.GetBox()
        area = f.GetArea if not callable(f.GetArea) else f.GetArea()
        dy = abs(box[4] - box[1])
        print(f"  Face {fi}: area={area}, dy={dy:.6f}, ymax={box[4]:.4f}")
        if dy < 0.002 and box[4] > best_y:
            best_y = box[4]
            best_face = f

if best_face:
    sel_res = best_face.Select4(False, engine.callout)
    print(f"5. Successfully selected top face via Select4: {sel_res}")

    # Now open sketch on top face and cut!
    sk_res = engine.start_sketch()
    print(f"start_sketch: {sk_res.ok}")
    c_res = engine.draw_circle(0.0, 0.0, 20.0)
    print(f"draw_circle: {c_res.ok}")
    cut_res = engine.extrude_cut(through_all=True)
    print(f"6. extrude_cut on top face: ok={cut_res.ok}, feat={cut_res.feature_name}")
    state = engine.get_model_state()
    print(f"7. Final state: bodies={state['body_count']}, box={state['box_max_mm']}")
else:
    print("Could not find top face!")
