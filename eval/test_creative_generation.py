import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cad_executor import run_autonomous_cad_agent

test_prompt = "Bana 6 kollu bir hexacopter gövdesi tasarla, kolları 280 mm uzunluğunda olsun, motor yuvaları ve ortasında petek hafifletme penceresi bulunsun"

print(f">>> TESTING CREATIVE AUTONOMOUS GENERATION: '{test_prompt}' <<<")
res = run_autonomous_cad_agent(
    user_prompt=test_prompt,
    max_retries=2,
    llm_backend="gemini",
    creativity_style="aerospace"
)

print(f"\nResult Success: {res['success']}")
print(f"Parça Adı: {res.get('parca_adi')}")
print(f"Attempts: {res.get('attempts')}")
print(f"Final Message: {res.get('message')}")
print(f"State: {res.get('state')}")
if 'plan' in res:
    print(f"Total Steps: {len(res['plan'].get('adimlar', []))}")
    print(json.dumps(res['plan'], indent=2, ensure_ascii=False))
