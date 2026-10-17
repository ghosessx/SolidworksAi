"""
Test revolve_boss on live SolidWorks to verify exact parameter signature.
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cad_engine import SolidWorksCADEngine

engine = SolidWorksCADEngine()
engine.new_part()
engine.select_plane("on")
engine.start_sketch()
engine.draw_centerline(0.0, 0.0, 100.0, 0.0)
engine.draw_line_chain([[0.0, 0.0], [0.0, 10.0], [100.0, 10.0], [100.0, 0.0]], close_loop=True)

# Test FeatureRevolve2 signatures
angle_rad = math.radians(360.0)
fm = engine.model.FeatureManager
engine.close_sketch()

print("Testing FeatureRevolve2...")
# SolidWorks API FeatureRevolve2:
# FeatureRevolve2(SingleDir, IsSolid, ReverseDir, BothDir, Dir1Thin, Angle1, Angle2, Dir1Draft, Dir1DraftAngle, Dir1DraftOutward, Dir2Thin, Angle2, Dir2Draft, Dir2DraftAngle, Dir2DraftOutward, Merge, UseFeatScope, UseAutoSelect)
try:
    feat = fm.FeatureRevolve2(
        True, True, False, False, False, angle_rad, 0.0,
        False, 0.0, False, False, 0.0, False, 0.0, False,
        True, True, True
    )
    print("FeatureRevolve2 with 18 args returned:", feat)
except Exception as e:
    print("18 args error:", e)

try:
    feat = fm.FeatureRevolve2(
        True, True, False, False, False, angle_rad, 0.0,
        False, 0.0, False, False, 0.0, 0.0, True, True, True
    )
    print("FeatureRevolve2 with 16 args returned:", feat)
except Exception as e:
    print("16 args error:", e)
