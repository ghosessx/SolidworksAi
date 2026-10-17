import os
import re
import sys
import json
import inspect
from collections import defaultdict

sys.path.insert(0, r"D:\SolidAI")

import settings
import cad_schema
import cad_engine
import mock_engine
import cad_simulator
import cad_executor
import vision_analyzer
import parametric_templates
import agent_prompt

print("=" * 70)
print("SOLIDAI CODEBASE AUDIT")
print("=" * 70)

# 1. Operation name parity
schema_ops = cad_schema.VALID_ENGINE_OPERATIONS
eng_methods = {m for m in dir(cad_engine.SolidWorksCADEngine) if not m.startswith("_")}
mock_methods = {m for m in dir(mock_engine.MockCADEngine) if not m.startswith("_")}

prompt_text = (
    agent_prompt.AGENT_SYSTEM_PROMPT + "\n" +
    str(agent_prompt.ALL_FEW_SHOT_LIBRARY) + "\n" +
    vision_analyzer.MASTER_BLUEPRINT_SYSTEM_PROMPT
)
ops_in_prompts = set(re.findall(r'["\']islem["\']\s*:\s*["\'](\w+)["\']', prompt_text))

print(f"\n1. OPERATION & METHOD CONSISTENCY:")
print(f"   - Schema registered operations: {len(schema_ops)}")
print(f"   - Engine methods: {len(eng_methods)}")
print(f"   - Mock engine methods: {len(mock_methods)}")
print(f"   - Operations referenced in prompts: {len(ops_in_prompts)}")

missing_in_engine = ops_in_prompts - eng_methods
missing_in_schema = ops_in_prompts - schema_ops
print(f"   -> In Prompts but MISSING in Engine: {missing_in_engine}")
print(f"   -> In Prompts but MISSING in Schema: {missing_in_schema}")
print(f"   -> In Engine but MISSING in MockEngine: {eng_methods - mock_methods}")
print(f"   -> In MockEngine but MISSING in Engine: {mock_methods - eng_methods}")

# 2. Parametric templates verification
print(f"\n2. PARAMETRIC TEMPLATES VERIFICATION:")
template_funcs = [
    f for name, f in inspect.getmembers(parametric_templates, inspect.isfunction)
    if name.startswith("generate_")
]
print(f"   - Total template generators: {len(template_funcs)}")
sim = cad_simulator.CADSimulator()
for tf in template_funcs:
    try:
        plan = tf()
        res = sim.simulate(plan)
        step_ops = {s.get("islem") or s.get("action") for s in plan.get("adimlar", []) or plan.get("steps", [])}
        unknown_steps = step_ops - eng_methods
        status = "OK" if res.valid and not unknown_steps else f"ERROR: errors={res.errors}, unknown={unknown_steps}"
        print(f"   - {tf.__name__}: {status}")
    except Exception as e:
        print(f"   - {tf.__name__}: INVOCATION ERROR ({e})")

# 3. Argument signature mismatch between SolidWorksCADEngine and MockCADEngine
print(f"\n3. METHOD SIGNATURE PARITY:")
sig_diffs = []
for m_name in eng_methods & mock_methods:
    f_eng = getattr(cad_engine.SolidWorksCADEngine, m_name)
    f_mock = getattr(mock_engine.MockCADEngine, m_name)
    try:
        sig_eng = inspect.signature(f_eng)
        sig_mock = inspect.signature(f_mock)
        params_eng = list(sig_eng.parameters.keys())
        params_mock = list(sig_mock.parameters.keys())
        if params_eng != params_mock:
            sig_diffs.append((m_name, params_eng, params_mock))
    except Exception:
        pass
if sig_diffs:
    for m_name, pe, pm in sig_diffs:
        print(f"   - {m_name}: cad_engine={pe} vs mock_engine={pm}")
else:
    print("   -> All method signatures are 100% identical.")

# 4. GUI & Code Quality Checks
print(f"\n4. GUI & INTEGRATION CHECKS:")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SolidAI_GUI.py"), "r", encoding="utf-8", errors="ignore") as f:
    gui_code = f.read()

gui_imports = re.findall(r'from (\w+) import|import (\w+)', gui_code)
gui_imported_modules = {a or b for a, b in gui_imports}
print(f"   - GUI imported modules: {sorted(gui_imported_modules)}")

if "run_vision_cad_agent" in gui_code:
    print("   - GUI -> run_vision_cad_agent integrated: YES")
else:
    print("   - GUI -> run_vision_cad_agent integrated: NO")

if "run_autonomous_cad_agent" in gui_code:
    print("   - GUI -> run_autonomous_cad_agent integrated: YES")
else:
    print("   - GUI -> run_autonomous_cad_agent integrated: NO")

# 5. Redundant / Dead Files & Bloat Analysis
print(f"\n5. REPOSITORY CLEANLINESS ANALYSIS:")
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_dir = os.path.join(base_dir, ".solidai_cache")
tools_dir = os.path.join(base_dir, "tools")
eval_dir = os.path.join(base_dir, "eval")

root_files = os.listdir(base_dir)
print(f"   - Root directory check:")
for rf in root_files:
    if rf.endswith(".png") or rf.endswith(".jpg") or rf.endswith(".tmp"):
        full = os.path.join(base_dir, rf)
        print(f"     * Temporary test image/file: {rf} ({os.path.getsize(full)} bytes)")

if os.path.exists(cache_dir):
    cache_files = os.listdir(cache_dir)
    print(f"   - Cache files in .solidai_cache: {len(cache_files)}")

if os.path.exists(tools_dir):
    tools_files = os.listdir(tools_dir)
    print(f"   - Diagnostic tools in tools/: {tools_files}")
