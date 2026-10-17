import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent_prompt
from cad_simulator import CADSimulator

sim = CADSimulator()
all_passed = True

print("=== VERIFYING ALL FEW-SHOT PLANS IN CAD SIMULATOR ===")
for cat, messages in agent_prompt.ALL_FEW_SHOT_LIBRARY.items():
    plan_json_str = messages[1]['content']
    plan = json.loads(plan_json_str)
    res = sim.simulate(plan)
    if res.valid:
        print(f"[PASS] {cat}: '{plan.get('parca_adi')}' -> Bodies: {res.final_state.get('body_count')}, Volume: {res.final_state.get('total_volume_mm3', 0):.1f} mm3")
    else:
        print(f"[FAIL] {cat}: {res.errors}")
        all_passed = False

if all_passed:
    print("\n>>> ALL FEW-SHOT PLANS FULLY VALIDATED AND FEASIBLE! <<<")
else:
    print("\n>>> SOME FEW-SHOT PLANS FAILED VALIDATION! <<<")
