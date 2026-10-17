"""
Test volume and mass properties on a fresh part in live SolidWorks.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cad_engine import SolidWorksCADEngine

engine = SolidWorksCADEngine()
engine.new_part()
engine.select_plane("ust")
engine.start_sketch()
engine.draw_center_rectangle(0.0, 0.0, 50.0, 50.0)
engine.extrude_boss(depth_mm=10.0)

# Rebuild
try:
    if callable(engine.model.EditRebuild3):
        engine.model.EditRebuild3()
except Exception:
    pass

# Method 1: Extension.CreateMassProperty
try:
    mp = engine.model.Extension.CreateMassProperty()
    print("CreateMassProperty exists:", mp is not None)
    if mp:
        print("mp.Volume:", mp.Volume)
        bodies = engine.model.GetBodies2(0, True)
        if bodies:
            print("bodies count:", len(bodies))
            res = mp.AddBodies(bodies)
            print("AddBodies returned:", res)
            print("mp.Volume after AddBodies:", mp.Volume)
except Exception as e:
    print("Method 1 error:", e)

# Method 2: Extension.GetMassProperties2
try:
    res2 = engine.model.Extension.GetMassProperties2(1, 0, False)
    print("GetMassProperties2 result:", res2)
except Exception as e:
    print("Method 2 error:", e)

# Method 3: Body2.GetMassProperties
try:
    bodies = engine.model.GetBodies2(0, True)
    if bodies:
        b = bodies[0]
        # Body2::GetMassProperties returns [CenterOfMassX, Y, Z, Volume, Area, Mass, ...]
        bmp = b.GetMassProperties(0)
        print("Body2.GetMassProperties:", bmp)
        if bmp and len(bmp) >= 4:
            print("Body volume (m3):", bmp[3], "volume (mm3):", bmp[3] * 1e9)
except Exception as e:
    print("Method 3 error:", e)
