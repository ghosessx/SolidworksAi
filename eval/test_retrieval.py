import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent_prompt

prompts = [
    'Bana 6 kollu bir hexacopter şasesi yap',
    'Cinewhoop drone şasesi, pervane korumalı',
    'FPV yarış kamerası için canopy yap',
    '240 mm quadcopter x-frame',
    'Hafifletilmiş robot mafsal linki',
    'Standart boru flanşı'
]

for p in prompts:
    shots = agent_prompt.get_relevant_few_shots(p)
    plan_data = json.loads(shots[1]['content'])
    print(f"Prompt: '{p}'")
    print(f"  -> Category Matched: {plan_data.get('parca_adi')}")
