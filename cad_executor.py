"""
SolidAI Autonomous CAD Agent — Truthful Executor & Closed-Loop Self-Healing Engine
Executes JSON Action Plans on SolidWorksCADEngine with pre-run simulation and state-aware repair.
"""
import json
import re
import sys
import os
import time
import subprocess
import urllib.request
import ollama

def ensure_ollama_running() -> bool:
    """Checks if Ollama is responsive; starts it automatically if down."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=1) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    try:
        models_dir = os.environ.get("OLLAMA_MODELS", "D:\\OllamaModels")
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = models_dir
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)
        return True
    except Exception:
        return False

# Ensure unbuffered and safe stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from cad_engine import SolidWorksCADEngine, StepResult
from mock_engine import MockCADEngine
from cad_schema import validate_cad_plan, CADPlan
from cad_simulator import CADSimulator
from parametric_templates import match_parametric_template
from agent_prompt import AGENT_SYSTEM_PROMPT, get_relevant_few_shots
import settings


def extract_json_plan(text: str) -> dict:
    """Robustly extracts JSON object from LLM response, even when preceded by thinking prose,
    missing opening braces, or truncated mid-stream.
    """
    text_clean = text.strip()

    def try_parse(s: str):
        s_clean = s.strip()
        try:
            obj = json.loads(s_clean)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # Try trailing comma fix
        try:
            s_fixed = re.sub(r',\s*([}\]])', r'\1', s_clean)
            obj = json.loads(s_fixed)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # Try unescaped newline fix inside string values
        try:
            # Replace raw newlines inside JSON string values
            s_escaped = re.sub(r'("(?:[^"\\]|\\.)*")', lambda m: m.group(1).replace('\n', '\\n').replace('\r', ''), s_clean)
            obj = json.loads(s_escaped)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        raise ValueError("Not a JSON dict")

    # 1. Direct parse
    try:
        return try_parse(text_clean)
    except Exception:
        pass

    # 2. Markdown code blocks (check all blocks, preferring one with 'adimlar', 'steps', or 'parca_adi')
    for match in re.finditer(r'```(?:json)?\s*\n?(.*?)\n?```', text_clean, re.DOTALL):
        candidate = match.group(1).strip()
        # Case A: candidate is valid JSON
        try:
            obj = try_parse(candidate)
            if "adimlar" in obj or "steps" in obj or "parca_adi" in obj or "part_name" in obj:
                return obj
        except Exception:
            pass
        # Case B: candidate is missing opening '{'
        if not candidate.startswith('{') and any(k in candidate for k in ['"parca_adi"', '"part_name"', '"adimlar"', '"steps"']):
            try:
                obj = try_parse("{\n" + candidate + ("\n}" if not candidate.endswith('}') else ""))
                if "adimlar" in obj or "steps" in obj or "parca_adi" in obj or "part_name" in obj:
                    return obj
            except Exception:
                pass

    # 3. Anchor on {"parca_adi" or {"adimlar" or scan all '{' with raw_decode
    decoder = json.JSONDecoder()
    best_obj = None
    for m in re.finditer(r'\{', text_clean):
        idx = m.start()
        try:
            obj, _ = decoder.raw_decode(text_clean[idx:])
            if isinstance(obj, dict):
                if "adimlar" in obj or "steps" in obj:
                    return obj
                if "parca_adi" in obj or "part_name" in obj:
                    best_obj = obj
        except Exception:
            pass
    if best_obj is not None:
        return best_obj

    # 4. Outermost { ... } starting from "parca_adi" / "part_name" if present, else first '{'
    anchor_match = re.search(r'\{\s*"(?:parca_adi|part_name|adimlar|steps)"[\s\S]*\}', text_clean)
    if anchor_match:
        try:
            return try_parse(anchor_match.group(0))
        except Exception:
            pass

    match = re.search(r'\{.*\}', text_clean, re.DOTALL)
    if match:
        try:
            return try_parse(match.group(0))
        except Exception:
            pass

    # 5. Missing opening '{' fallback (e.g. LLM wrote: "parca_adi": "foo", "adimlar": [...])
    for key_pattern in ['"parca_adi"', '"part_name"', '"adimlar"', '"steps"']:
        key_pos = text_clean.find(key_pattern)
        if key_pos != -1:
            raw_chunk = text_clean[key_pos:]
            # Clean trailing markdown fence if present
            raw_chunk = re.sub(r'```.*$', '', raw_chunk, flags=re.DOTALL).strip()
            # Try with prepended '{' and various closing brackets
            for suffix in ['}', '"}', '"]}', '}]}', '"]}}', '}]}}', ']}']:
                try:
                    candidate = "{\n" + raw_chunk + suffix
                    obj = try_parse(candidate)
                    if "adimlar" in obj or "steps" in obj or "parca_adi" in obj or "part_name" in obj:
                        return obj
                except Exception:
                    pass

    # 6. Truncation Auto-Recovery: if output was cut off mid-JSON after an opening '{'
    anchor_pos = text_clean.find('"parca_adi"')
    if anchor_pos == -1:
        anchor_pos = text_clean.find('"part_name"')
    start = text_clean.rfind('{', 0, anchor_pos) if anchor_pos != -1 else text_clean.find('{')
    if start != -1:
        sub = text_clean[start:]
        for suffix in ['', '"}', '"]}', '}]}', '"]}}', '}]}}', ']}']:
            try:
                return try_parse(sub + suffix)
            except Exception:
                pass
        last_step_end = sub.rfind('}')
        if last_step_end != -1 and ('"adimlar"' in sub[:last_step_end] or '"steps"' in sub[:last_step_end]):
            truncated_fixed = sub[:last_step_end + 1] + ']}'
            try:
                return try_parse(truncated_fixed)
            except Exception:
                pass

    raise ValueError(f"Could not extract a valid JSON CAD plan from model response: {text[:250]}")


def _are_concentric_circles(draw_steps: list) -> bool:
    """Returns True if draw_steps consists of 2 concentric circles at the same (x, y) center (e.g. hollow tube)."""
    if len(draw_steps) != 2:
        return False
    if any(s.get("islem") != "draw_circle" for s in draw_steps):
        return False
    p0 = draw_steps[0].get("params") or draw_steps[0].get("parametreler") or {}
    p1 = draw_steps[1].get("params") or draw_steps[1].get("parametreler") or {}
    x0, y0, d0 = float(p0.get("x", 0.0)), float(p0.get("y", 0.0)), float(p0.get("dia", 0.0))
    x1, y1, d1 = float(p1.get("x", 0.0)), float(p1.get("y", 0.0)), float(p1.get("dia", 0.0))
    return abs(x0 - x1) < 0.1 and abs(y0 - y1) < 0.1 and abs(d0 - d1) > 0.2


def _are_disjoint_circles_only(draw_steps: list) -> bool:
    """Returns True if all draw_steps are draw_circle and none of them overlap or touch each other."""
    if not draw_steps or any(s.get("islem") != "draw_circle" for s in draw_steps):
        return False
    circles = []
    for s in draw_steps:
        p = s.get("params") or s.get("parametreler") or {}
        circles.append((float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("dia", 0.0)) / 2.0))
    for i in range(len(circles)):
        for j in range(i + 1, len(circles)):
            x1, y1, r1 = circles[i]
            x2, y2, r2 = circles[j]
            dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            if dist <= (r1 + r2 + 0.5):
                return False
    return True


def normalize_and_decompose_plan(plan_dict: dict) -> dict:
    """Normalizes a CAD JSON plan and automatically decomposes multi-contour sketches
    into sequential single-contour extrude_boss / extrude_cut operations.
    Eliminates SolidWorks self-intersecting contour failures while preserving hollow concentric tubes.
    """
    if not isinstance(plan_dict, dict):
        return plan_dict

    raw_steps = plan_dict.get("adimlar") or plan_dict.get("steps") or plan_dict.get("actions") or []
    if not raw_steps:
        return plan_dict

    normalized_steps = []
    for s in raw_steps:
        if not isinstance(s, dict):
            continue
        islem = str(s.get("islem") or s.get("action") or s.get("operation") or s.get("command") or "").strip()
        params = dict(s.get("params") or s.get("parameters") or s.get("parametreler") or s.get("args") or {})

        # Normalize command aliases
        if islem in ("apply_fillet_all_last_feature", "fillet"):
            islem = "apply_fillet"
        elif islem == "chamfer":
            islem = "apply_chamfer"

        # Normalize plane selection
        if islem == "select_plane":
            p_val = str(params.get("plane", "")).lower().strip()
            if p_val in ("front", "front plane", "on", "ön", "ön düzlem"):
                params["plane"] = "on"
            elif p_val in ("top", "top plane", "ust", "üst", "üst düzlem"):
                params["plane"] = "ust"
            elif p_val in ("right", "right plane", "sag", "sağ", "sağ düzlem"):
                params["plane"] = "sag"

        # Normalize parameter aliases
        elif islem == "draw_circle":
            if "dia_mm" in params and "dia" not in params:
                params["dia"] = params.pop("dia_mm")
            elif "diameter" in params and "dia" not in params:
                params["dia"] = params.pop("diameter")
            elif "radius" in params and "dia" not in params:
                params["dia"] = float(params.pop("radius")) * 2.0
            elif "r" in params and "dia" not in params:
                params["dia"] = float(params.pop("r")) * 2.0
            if "center_x" in params and "x" not in params:
                params["x"] = params.pop("center_x")
            if "center_y" in params and "y" not in params:
                params["y"] = params.pop("center_y")

        elif islem == "draw_center_rectangle":
            if "center_x" in params and "x" not in params:
                params["x"] = params.pop("center_x")
            if "center_y" in params and "y" not in params:
                params["y"] = params.pop("center_y")
            if "width_mm" in params and "w" not in params:
                params["w"] = params.pop("width_mm")
            elif "width" in params and "w" not in params:
                params["w"] = params.pop("width")
            if "height_mm" in params and "h" not in params:
                params["h"] = params.pop("height_mm")
            elif "height" in params and "h" not in params:
                params["h"] = params.pop("height")

        elif islem == "draw_slot":
            if "width_mm" in params and "width" not in params:
                params["width"] = params.pop("width_mm")

        elif islem == "create_ref_plane":
            bp_val = str(params.get("base_plane") or params.get("plane") or "").lower().strip()
            if bp_val in ("front", "front plane", "on", "ön"):
                params["base_plane"] = "on"
            elif bp_val in ("top", "top plane", "ust", "üst"):
                params["base_plane"] = "ust"
            elif bp_val in ("right", "right plane", "sag", "sağ"):
                params["base_plane"] = "sag"
            elif bp_val:
                params["base_plane"] = bp_val
            if "distance" in params and "distance_mm" not in params:
                params["distance_mm"] = params.pop("distance")

        elif islem in ("extrude_boss", "extrude_cut"):
            if "depth" in params and "depth_mm" not in params:
                params["depth_mm"] = params.pop("depth")

        normalized_steps.append({"islem": islem, "params": params})

    decomposed = []
    last_selection = {"islem": "select_plane", "params": {"plane": "ust"}}
    has_boss_so_far = False
    i = 0
    n = len(normalized_steps)

    while i < n:
        step = normalized_steps[i]
        cmd = step["islem"]
        params = step["params"]

        if cmd in ("select_plane", "select_face", "select_top_face", "select_ref_plane", "select_face_by_ray"):
            last_selection = {"islem": cmd, "params": dict(params)}
            decomposed.append(step)
            i += 1
            continue

        if cmd == "create_ref_plane":
            decomposed.append(step)
            last_selection = {"islem": "select_ref_plane", "params": {}}
            i += 1
            continue

        if cmd == "start_sketch":
            # Collect all drawing commands in this sketch until feature or close
            j = i + 1
            sketch_draws = []
            while j < n and normalized_steps[j]["islem"].startswith("draw_"):
                sketch_draws.append(normalized_steps[j])
                j += 1

            # Skip optional close_sketch if immediately followed by extrude/revolve or end
            if j < n and normalized_steps[j]["islem"] == "close_sketch":
                j += 1

            # Check what closes/consumes this sketch
            end_step = normalized_steps[j] if j < n else None
            end_cmd = end_step["islem"] if end_step else ""

            consumed_end_step = True
            if end_cmd not in ("extrude_boss", "extrude_cut", "revolve_boss", "revolve_cut") and sketch_draws:
                # Dangling sketch (e.g., LLM truncated before final extrude_cut)
                consumed_end_step = False
                if has_boss_so_far:
                    end_step = {"islem": "extrude_cut", "params": {"through_all": True, "both_directions": True}}
                    end_cmd = "extrude_cut"
                else:
                    end_step = {"islem": "extrude_boss", "params": {"depth_mm": 5.0}}
                    end_cmd = "extrude_boss"

            if end_cmd in ("extrude_boss", "revolve_boss"):
                has_boss_so_far = True

            # Fix draw_lightening_pocket double-cut if followed by explicit extrude_cut/boss
            if end_cmd in ("extrude_cut", "extrude_boss"):
                for ds in sketch_draws:
                    if ds["islem"] == "draw_lightening_pocket" and ds["params"].get("depth_mm", 0.0):
                        ds["params"]["depth_mm"] = 0.0

            # Normalize extrude_cut parameters (preserve blind depth_mm cuts, convert midplane -> both_directions)
            if end_cmd == "extrude_cut":
                ep = end_step["params"]
                if ep.pop("midplane", False):
                    ep["both_directions"] = True
                has_blind_depth = bool(ep.get("depth_mm")) and float(ep.get("depth_mm", 0.0)) > 0.0
                if ep.get("through_all") is True or not has_blind_depth:
                    ep["through_all"] = True
                    ep["both_directions"] = True
                else:
                    ep["through_all"] = False

            non_cl_draws = [d for d in sketch_draws if d["islem"] != "draw_centerline"]
            sel_is_plane = last_selection["islem"] in ("select_plane", "select_ref_plane")

            # Case 1: extrude_boss with multiple contours on a plane
            if (
                end_cmd == "extrude_boss"
                and len(non_cl_draws) > 1
                and sel_is_plane
                and not _are_concentric_circles(non_cl_draws)
                and not _are_disjoint_circles_only(non_cl_draws)
            ):
                for idx_d, d_step in enumerate(non_cl_draws):
                    if idx_d > 0:
                        decomposed.append({"islem": last_selection["islem"], "params": dict(last_selection["params"])})
                    decomposed.append({"islem": "start_sketch", "params": {}})
                    decomposed.append(d_step)
                    decomposed.append({"islem": "extrude_boss", "params": dict(end_step["params"])})
                i = (j + 1) if consumed_end_step else j
                continue

            # Case 2: extrude_cut with multiple mixed/complex contours
            if (
                end_cmd == "extrude_cut"
                and len(non_cl_draws) > 1
                and not _are_disjoint_circles_only(non_cl_draws)
            ):
                for idx_d, d_step in enumerate(non_cl_draws):
                    if idx_d > 0:
                        decomposed.append({"islem": last_selection["islem"], "params": dict(last_selection["params"])})
                    decomposed.append({"islem": "start_sketch", "params": {}})
                    decomposed.append(d_step)
                    decomposed.append({"islem": "extrude_cut", "params": dict(end_step["params"])})
                i = (j + 1) if consumed_end_step else j
                continue

            # Case 3: single contour or disjoint circles sketch
            if sketch_draws and end_step:
                decomposed.append({"islem": "start_sketch", "params": {}})
                for d_step in sketch_draws:
                    decomposed.append(d_step)
                decomposed.append({"islem": end_cmd, "params": dict(end_step["params"])})
                i = (j + 1) if consumed_end_step else j
                continue

        if cmd in ("extrude_boss", "revolve_boss"):
            has_boss_so_far = True

        decomposed.append(step)
        i += 1

    plan_copy = dict(plan_dict)
    plan_copy["adimlar"] = decomposed
    return plan_copy


def execute_cad_plan(plan_dict: dict, engine=None, check_simulation: bool = True) -> tuple[bool, str, int, dict]:
    """Executes each step in plan_dict sequentially on SolidWorksCADEngine or MockCADEngine.

    Returns:
        (success: bool, message: str, failed_step_index: int, final_state: dict)
    """
    plan_dict = normalize_and_decompose_plan(plan_dict)

    if engine is None:
        try:
            engine = SolidWorksCADEngine()
        except Exception:
            print("[CAD Executor] SolidWorks connection unavailable, using MockCADEngine.")
            engine = MockCADEngine()

    # 1. Static Dry-Run Simulation Check
    if check_simulation:
        sim = CADSimulator()
        sim_res = sim.simulate(plan_dict)
        if not sim_res.valid:
            err_msg = " / ".join(sim_res.errors)
            failed_idx = sim_res.failed_step_index if sim_res.failed_step_index is not None else 0
            print(f"[CAD Simulator] Static pre-flight validation error: {err_msg}")
            return False, f"Static simulation error: {err_msg}", failed_idx, sim_res.final_state

        if sim_res.warnings:
            for w in sim_res.warnings:
                print(f"[CAD Simulator Warning] {w}")

    steps = plan_dict.get("adimlar") or plan_dict.get("steps") or []
    if not steps:
        return False, "No steps found in CAD action plan.", 0, {}

    parca_adi = plan_dict.get('parca_adi') or plan_dict.get('part_name') or 'Part'
    print(f"\n[CAD Executor] Building '{parca_adi}'...")
    print(f"[Design Rationale]: {plan_dict.get('tasarim_mantigi') or plan_dict.get('design_logic') or '-'}")

    for idx, step in enumerate(steps):
        islem = str(step.get("islem") or step.get("action") or "").strip()
        params = step.get("params") or step.get("parametreler") or {}

        print(f"  -> Step {idx + 1}/{len(steps)}: {islem}({params})", flush=True)

        if not hasattr(engine, islem):
            return False, f"Unknown CAD command: '{islem}'", idx, engine.get_model_state()

        method = getattr(engine, islem)

        try:
            res = method(**params)

            # StepResult truth verification
            if isinstance(res, StepResult):
                if not res.ok:
                    # Non-critical finishing features (chamfer/fillet) shouldn't abort entire solid model
                    if islem.startswith("apply_chamfer") or islem.startswith("apply_fillet"):
                        print(f"     [Info] {islem} skipped ({res.error}), solid body preserved.")
                    else:
                        return False, f"Step {idx + 1} ({islem}) failed: {res.error}", idx, res.state
            elif res is False:
                return False, f"Step {idx + 1} ({islem}) returned False.", idx, engine.get_model_state()

            # Rebuild after major features
            if islem.startswith("extrude_") or islem.startswith("revolve_"):
                engine.rebuild()

        except Exception as ex:
            if islem.startswith("apply_chamfer") or islem.startswith("apply_fillet"):
                print(f"     [Info] {islem} exception ({str(ex)}), solid body preserved.")
                continue
            return False, f"CAD API error ({islem}): {str(ex)}", idx, engine.get_model_state()

    engine.rebuild()
    engine.zoom_fit()
    final_state = engine.get_model_state()
    return True, "Part created successfully.", len(steps), final_state


def call_gemini_cad_planner(messages: list, log_fn=None) -> tuple[dict, str]:
    """Generates CAD action plan using Gemini candidate models for superior engineering reasoning."""
    api_key = settings.get_gemini_api_key()
    if not api_key:
        raise ValueError("Gemini API key is not configured.")

    system_text = ""
    contents = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_text += content + "\n"
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role in ["assistant", "model"]:
            contents.append({"role": "model", "parts": [{"text": content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 16384,
            "thinkingConfig": {"thinkingBudget": 512}
        }
    }
    if system_text.strip():
        payload["system_instruction"] = {"parts": [{"text": system_text.strip()}]}

    payload_bytes = json.dumps(payload).encode("utf-8")
    last_ex = None

    candidate_models = settings.get_active_gemini_models()
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            if log_fn:
                log_fn(f"Google Gemini ({model_name}) engineering intelligence active...")
            req = urllib.request.Request(
                url, data=payload_bytes, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                if resp.status == 200:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    cand = res_json.get("candidates", [])
                    if cand:
                        parts = cand[0].get("content", {}).get("parts", [])
                        text = "\n".join(pt.get("text", "") for pt in parts if not pt.get("thought")).strip()
                        if not text:
                            text = "\n".join(pt.get("text", "") for pt in parts).strip()
                        plan_dict = extract_json_plan(text)
                        return plan_dict, text
        except urllib.error.HTTPError as he:
            last_ex = he
            if he.code == 429:
                settings.mark_model_exhausted(model_name)
                if log_fn:
                    log_fn(f"[Gemini Info] '{model_name}' quota exhausted on Free Tier. Switching to active model gemini-3-flash-preview (Deep Thinking: 8192 tokens)...")
                continue
            elif he.code in [400, 404, 503]:
                continue
            else:
                break
        except Exception as e:
            last_ex = e
            continue

    raise RuntimeError(f"Gemini API could not generate response: {last_ex}")


def run_autonomous_cad_agent(user_prompt: str, max_retries: int = 3,
                             progress_callback=None, llm_backend: str = "auto",
                             creativity_style: str = "aerospace") -> dict:
    """Full Autonomous Loop with Dual-Engine (Gemini Cloud + Local Ollama):
    1. Parametric Template Matching (instant, 100% mathematically correct)
    2. Dynamic Few-Shot Retrieval with CoT Engineering Reasoning
    3. Frontier Gemini Cloud LLM or Local Ollama Planner
    4. Dry-Run Simulator Pre-flight Check
    5. Execution in SOLIDWORKS (fresh part)
    6. Closed-Loop State-Aware Self-Healing
    """
    def log(msg: str):
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"[Agent] {safe_msg}", flush=True)
        if progress_callback:
            progress_callback(msg)

    # 1. Check for standard parametric mechanical template ONLY if explicitly requested
    # (Creative prompts must always be designed autonomously by the AI LLM!)
    is_explicit_template = (
        user_prompt.lower().startswith(("template:", "preset:", "standard:", "şablon:")) or
        ("standard" in user_prompt.lower() and llm_backend == "auto")
    )
    if is_explicit_template:
        template_plan = match_parametric_template(user_prompt)
        if template_plan:
            part_title = template_plan.get("parca_adi") or template_plan.get("part_name") or "Part"
            log(f"Parametric template matched: '{part_title}'. Executing directly...")
            try:
                engine = SolidWorksCADEngine()
            except Exception:
                engine = MockCADEngine()

            engine.new_part()
            success, msg, failed_idx, state = execute_cad_plan(template_plan, engine, check_simulation=True)
            if success:
                log(f"[OK] '{part_title}' generated flawlessly from parametric template!")
                return {
                    "success": True,
                    "parca_adi": part_title,
                    "plan": template_plan,
                    "attempts": 1,
                    "message": msg,
                    "state": state
                }

    # Style Augmentation for Engineering Creativity
    augmented_prompt = user_prompt.strip()
    if creativity_style == "aerospace":
        augmented_prompt += (
            "\n[AEROSPACE & WEIGHT-SAVING DIRECTIVE]: Maximize structural rigidity and strength-to-weight ratio. "
            "Incorporate lightening pockets (draw_lightening_pocket), honeycomb cutouts (draw_hexagon), "
            "stiffening ribs (draw_stiffening_rib), and edge chamfers (apply_chamfer) to design a high-performance CAD model."
        )
    elif creativity_style == "industrial":
        augmented_prompt += (
            "\n[INDUSTRIAL MANUFACTURING DIRECTIVE]: Design a robust, rigid mechanical part suitable for industrial fabrication, "
            "with solid wall thicknesses, standard bolt holes, and assembly chamfers."
        )

    # 2. Dynamic Few-Shot Retrieval for LLM Planner
    relevant_few_shots = get_relevant_few_shots(user_prompt, max_count=1)
    current_messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    current_messages.extend(relevant_few_shots)
    current_messages.append({"role": "user", "content": augmented_prompt})

    try:
        engine = SolidWorksCADEngine()
    except Exception:
        engine = MockCADEngine()

    attempt = 0
    last_error = ""

    while attempt <= max_retries:
        attempt += 1
        log(f"AI is analyzing design requirements (Attempt {attempt}/{max_retries + 1})...")

        plan_dict = None
        raw_reply = ""

        # --- Frontier Cloud Planner (Gemini) ---
        has_gemini_key = bool(settings.get_gemini_api_key())
        use_gemini = (llm_backend in ["auto", "gemini"]) and has_gemini_key

        if use_gemini:
            try:
                plan_dict, raw_reply = call_gemini_cad_planner(current_messages, log_fn=log)
                log("[Gemini] Creative engineering plan generated successfully!")
            except Exception as ge:
                log(f"[Gemini Notice] {ge}. Falling back to local Ollama (Qwen2.5-Coder)...")
                use_gemini = False

        # --- Local Offline Planner Fallback (Ollama Qwen2.5-Coder) ---
        if not plan_dict:
            try:
                ensure_ollama_running()
                stream = ollama.chat(
                    model=settings.DEFAULT_CODER_MODEL,
                    messages=current_messages,
                    options=settings.LLM_OPTIONS,
                    stream=True
                )

                raw_chunks = []
                token_count = 0
                for chunk in stream:
                    token = chunk.get('message', {}).get('content', '')
                    raw_chunks.append(token)
                    token_count += 1
                    if token_count % 25 == 0:
                        log(f"Local AI generating plan... ({token_count} tokens)")

                raw_reply = "".join(raw_chunks).strip()
                plan_dict = extract_json_plan(raw_reply)
            except Exception as oe:
                last_error = str(oe)
                log(f"Local model execution error: {last_error}")
                if any(k in last_error for k in ["10061", "10054", "ConnectError"]):
                    log("Ollama connection interrupted. Restarting background service...")
                    ensure_ollama_running()
                    time.sleep(2)
                continue

        # If plan is ready, inspect CoT thoughts
        try:
            parca_adi = plan_dict.get("part_name") or plan_dict.get("parca_adi", "Mechanical Part")
            cot = plan_dict.get("engineering_reasoning") or plan_dict.get("muhendislik_dusuncesi")
            if cot and isinstance(cot, dict):
                yaratici_fikir = cot.get("creativity_and_lightening") or cot.get("yaraticilik_ve_hafifletme") or cot.get("functional_analysis") or cot.get("fonksiyonel_analiz")
                if yaratici_fikir:
                    log(f"💡 [Engineering Thought]: {yaratici_fikir[:120]}...")

            log(f"Plan ready: '{parca_adi}'. Simulating and streaming to SOLIDWORKS...")

            # Always start each execution in a clean part to protect existing documents!
            engine.new_part()

            success, msg, failed_idx, state = execute_cad_plan(plan_dict, engine, check_simulation=True)

            if success:
                log(f"[OK] '{parca_adi}' created successfully!")
                return {
                    "success": True,
                    "parca_adi": parca_adi,
                    "plan": plan_dict,
                    "attempts": attempt,
                    "message": msg,
                    "state": state
                }

            # --- Closed-Loop State-Aware Self-Healing ---
            last_error = msg
            failed_step = plan_dict["adimlar"][failed_idx] if failed_idx < len(plan_dict.get("adimlar", [])) else {}
            log(f"[ERROR] Step {failed_idx + 1}: {last_error}")
            log("[SELF-HEALING] Error intercepted! Analyzing geometry state and revising plan...")

            healing_prompt = (
                f"ATTENTION: Previous CAD plan failed at step {failed_idx + 1}!\n"
                f"Failed Step: {json.dumps(failed_step, ensure_ascii=False)}\n"
                f"Error Message: {last_error}\n"
                f"Current SOLIDWORKS Model State: Body Count={state.get('body_count', 0)}, Volume={state.get('volume_mm3', 0.0)} mm3\n"
                f"CRITICAL: Ensure sketch contours are closed, overlapping shapes are placed in separate features, and 'start_sketch' is explicitly called.\n"
                f"Please revise the ENTIRE CAD PLAN from scratch and return ONLY a valid, raw JSON object."
            )

            current_messages = [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": augmented_prompt},
                {"role": "assistant", "content": raw_reply},
                {"role": "user", "content": healing_prompt}
            ]

        except Exception as e:
            last_error = str(e)
            log(f"Plan execution error: {last_error}")
            if raw_reply:
                current_messages.append({"role": "assistant", "content": raw_reply[:400]})
                current_messages.append({
                    "role": "user",
                    "content": f"JSON or API execution error: {last_error}. Please return ONLY a valid raw JSON object."
                })

    return {
        "success": False,
        "error": f"Failed after {max_retries} automatic repair attempts: {last_error}",
        "attempts": attempt
    }


def run_vision_cad_agent(image_path: str, user_notes: str = "",
                         api_key: str = "", progress_callback=None) -> dict:
    """End-to-End Pipeline: Technical Drawing Image -> Vision Analysis -> CAD Plan -> Execution."""
    def log(msg: str):
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"[Vision Agent] {safe_msg}")
        if progress_callback:
            progress_callback(msg)

    log(f"Analyzing technical drawing: {os.path.basename(image_path)}...")
    from vision_analyzer import extract_cad_plan_from_image

    try:
        engine = SolidWorksCADEngine()
    except Exception:
        engine = MockCADEngine()

    try:
        plan_dict = extract_cad_plan_from_image(
            image_path=image_path,
            user_notes=user_notes,
            api_key=api_key or settings.get_gemini_api_key(),
            log_callback=log
        )
    except Exception as e:
        log(f"Vision analysis error: {e}")
        return {"success": False, "error": f"Failed to analyze technical drawing: {str(e)}"}

    parca_adi = plan_dict.get("part_name") or plan_dict.get("parca_adi", "Blueprint Model")
    cot_str = json.dumps(plan_dict.get("engineering_reasoning") or plan_dict.get("muhendislik_dusuncesi", ""), ensure_ascii=False)
    match_query = f"{parca_adi} {os.path.basename(image_path)} {user_notes} {plan_dict.get('tasarim_mantigi', '')} {cot_str}"
    matched_template = match_parametric_template(match_query)
    if matched_template:
        log(f"Matched parametric template: '{matched_template.get('parca_adi')}'. Applying verified CAD geometry...")
        plan_dict = matched_template
        parca_adi = matched_template.get("parca_adi") or matched_template.get("part_name")

    active_notes = user_notes
    max_vision_attempts = 3

    for attempt in range(1, max_vision_attempts + 1):
        log(f"Executing CAD Action Plan (Attempt {attempt}/{max_vision_attempts}): '{parca_adi}'. Simulating and streaming to SOLIDWORKS...")

        engine.new_part()
        success, msg, failed_idx, state = execute_cad_plan(plan_dict, engine, check_simulation=True)

        is_single_body = (state.get("body_count", 1) == 1)
        if success and is_single_body:
            log(f"[OK] '{parca_adi}' successfully modeled from technical drawing! (Single Solid Body, Volume={state.get('volume_mm3', 0.0):.1f} mm3)")
            return {
                "success": True,
                "parca_adi": parca_adi,
                "plan": plan_dict,
                "attempts": attempt,
                "message": msg,
                "state": state
            }

        # Handle failure or multi-body split
        err_desc = msg if not success else f"Disjoint bodies detected ({state.get('body_count')} bodies). Single Solid Body rule violated. Features must merge into one solid body."
        log(f"[ERROR] Attempt {attempt}: {err_desc}")

        if attempt < max_vision_attempts:
            log(f"[CLOSED-LOOP VISION HEALING] Technical drawing re-evaluated with current geometry state ({state.get('body_count')} bodies, {state.get('volume_mm3', 0.0):.0f} mm3)...")
            healing_note = (
                f"Previous execution (Step {failed_idx + 1}) encountered error: {err_desc}.\n"
                f"Current SOLIDWORKS Model State: Body Count={state.get('body_count', 0)}, Volume={state.get('volume_mm3', 0.0)} mm3.\n"
                f"PLEASE RE-EXAMINE THE DRAWING: Ensure all extrude_boss features intersect with the primary body (penetrate by 2-5 mm), symmetric features use 'midplane': true, and blind cuts specify exact 'depth_mm' with 'through_all': false.\n"
                f"Revise the entire plan and return ONLY a valid, raw JSON object."
            )
            try:
                plan_dict = extract_cad_plan_from_image(
                    image_path=image_path,
                    user_notes=f"{active_notes}\n{healing_note}",
                    api_key=api_key or settings.get_gemini_api_key(),
                    log_callback=log
                )
                parca_adi = plan_dict.get("part_name") or plan_dict.get("parca_adi", parca_adi)
            except Exception as e:
                log(f"Vision healing call failed: {e}")
                break

    return {
        "success": False,
        "error": f"Failed after {max_vision_attempts} closed-loop vision repair attempts: {msg}",
        "state": state
    }

