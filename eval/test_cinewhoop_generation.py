import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cad_executor import run_autonomous_cad_agent

test_prompt = "Pervanelerin etrafında dairesel koruma halkaları (ducts) olan 3 inçlik bir cinewhoop drone şasesi yap, FC kulesi ve batarya yarıkları olsun"

def log_cb(msg):
    print(f"[TEST LOG] {msg}", flush=True)

print(f">>> TESTING CINWHOOP CREATIVE AUTONOMOUS GENERATION <<<", flush=True)
res = run_autonomous_cad_agent(
    user_prompt=test_prompt,
    max_retries=2,
    llm_backend="gemini",
    creativity_style="aerospace",
    progress_callback=log_cb
)

print(f"\nResult Success: {res['success']}", flush=True)
print(f"Parça Adı: {res.get('parca_adi')}", flush=True)
print(f"Attempts: {res.get('attempts')}", flush=True)
print(f"Final Message: {res.get('message')}", flush=True)
print(f"State: {res.get('state')}", flush=True)
if 'plan' in res:
    print(f"Total Steps: {len(res['plan'].get('adimlar', []))}", flush=True)
    print(json.dumps(res['plan'], indent=2, ensure_ascii=False), flush=True)

