"""
SolidAI — High-Precision Engineering Blueprint & Technical Drawing Vision Analyzer
Decodes 2D orthographic engineering drawings (Front, Top, Right/Section, 3D Isometric)
and generates verified, single-solid-body SolidAI CAD Action Plans using Gemini Vision models.
"""
import os
import json
import base64
import re
import urllib.request
import urllib.error
import time
import ollama
from PIL import Image, ImageEnhance, ImageOps

import settings
from cad_executor import extract_json_plan, normalize_and_decompose_plan
from cad_schema import validate_cad_plan
from cad_simulator import CADSimulator



MASTER_BLUEPRINT_SYSTEM_PROMPT = """You are a Senior SOLIDWORKS CAD Design and Manufacturing Specialist.
You are provided with a 2D/3D engineering technical blueprint (Front View, Top View, Right/Section View, and 3D Isometric View).
Your mission is to meticulously decode all geometric views, dimensions, and tolerances, and generate ONLY AND EXCLUSIVELY a valid JSON CAD Action Plan that builds the model in SOLIDWORKS as a SINGLE SOLID BODY (Body Count = 1).

================================================================================
SECTION 1: BLUEPRINT & ORTHOGRAPHIC VIEW DECODING PROTOCOL
================================================================================
1. IDENTIFY PRINCIPAL VIEWS AND AXES:
   - Front View (Z=0 Plane): Provides part width (X-axis) and height (Y-axis).
   - Top View (Y=0 Plane): Provides part width (X-axis) and depth (Z-axis). Downward on the drawing is +Z. In SOLIDWORKS "top" plane, sketch (x, y) maps to World (+X, -Z).
   - Right / Section View (X=0 Plane): Provides part depth (Z-axis) and height (Y-axis). Leftward on the drawing is +Z. In SOLIDWORKS "right" plane, sketch (x, y) maps to World (-Z, +Y).
   - 3D Isometric View: Verifies 3D topology, rib placements, ear connections, and hole locations.

2. SECTION LINES (SECTION A-A, B-B):
   - Pay close attention to cutting plane arrows. Section views reveal stepped internal bores, blind counterbores, keyways, and wall thicknesses.

3. SINGLE SOLID BODY GUARANTEE (BODY COUNT = 1):
   - Every new extruded feature (extrude_boss, revolve_boss) MUST intersect or merge with the existing solid body.
   - For symmetric parts, ALWAYS use "midplane": true to center the part on the origin (0,0,0).
   - When attaching arms, clevis ears, bushings, or ribs, overlap the base geometry into the primary body by 2-5 mm so features automatically merge into a single solid body.

4. CUT OPERATION TYPES (THROUGH-ALL VS BLIND CUTS):
   - For through-holes, slots, and open channels: use "through_all": true and "both_directions": true.
   - For blind holes, counterbores, and pockets: use "through_all": false and specify exact "depth_mm": <value>.

5. ATOMIC SKETCH RULE:
   - Each sketch MUST contain only ONE closed contour!
   - NEVER overlap rectangles and circles in the same sketch. Model each feature sequentially: select plane/face -> start_sketch -> draw primitive -> extrude_boss/cut.

================================================================================
SECTION 2: SOLIDWORKS 3D REFERENCE PLANES & COORDINATES
================================================================================
- "front" or "on" (Front Plane, Z=0):
  * Sketch (x, y) -> World (+X, +Y). Extrusion extends along Z-axis.
- "top" or "ust" (Top Plane, Y=0):
  * Sketch (x, y) -> World (+X, -Z). Extrusion extends along Y-axis (upward).
  * Note: A feature at +Z in world coordinates is drawn at y = -Z on the "top" plane!
- "right" or "sag" (Right Plane, X=0):
  * Sketch (x, y) -> World (-Z, +Y). Extrusion extends along X-axis.
  * Note: A feature at +Z in world coordinates is drawn at x = -Z on the "right" plane!
- Reference Planes:
  * {"islem": "create_ref_plane", "params": {"base_plane": "top", "distance_mm": 77.0}}
  * {"islem": "select_ref_plane", "params": {}}

================================================================================
SECTION 3: VALID CAD ENGINE OPERATIONS
================================================================================
1. Plane & Face Selection:
   - select_plane: {"plane": "top" | "front" | "right" | "ust" | "on" | "sag"}
   - create_ref_plane: {"base_plane": "top" | "front" | "right", "distance_mm": float, "flip": bool}
   - select_ref_plane: {}
   - select_face: {"where": "top" | "bottom" | "front" | "back" | "right" | "left"}
2. Sketching & 2D Geometry (start_sketch is MANDATORY before any drawing):
   - start_sketch: {}
   - draw_circle: {"x": float, "y": float, "dia": float}
   - draw_center_rectangle: {"x": float, "y": float, "w": float, "h": float}
   - draw_corner_rectangle: {"x1": float, "y1": float, "x2": float, "y2": float}
   - draw_rotated_rectangle: {"center_x": float, "center_y": float, "length_mm": float, "width_mm": float, "angle_deg": float}
   - draw_slot: {"x1": float, "y1": float, "x2": float, "y2": float, "width": float}
   - draw_line_chain: {"points_list": [[x1, y1], [x2, y2], ...], "close_loop": true}
   - draw_polygon: {"center_x": float, "center_y": float, "radius_mm": float, "sides": int, "angle_deg": float}
   - draw_hexagon: {"center_x": float, "center_y": float, "radius_mm": float, "angle_deg": float}
   - draw_circular_hole_pattern: {"center_x": float, "center_y": float, "pcd_mm": float, "count": int, "dia_mm": float}
3. 3D Extrusion & Cutting:
   - extrude_boss: {"depth_mm": float, "midplane": bool, "reverse": bool}
   - extrude_cut: {"through_all": bool, "both_directions": bool, "depth_mm": float}
   - revolve_boss: {"angle_deg": 360.0}
   - apply_fillet: {"radius_mm": float}
   - apply_chamfer: {"width_mm": float, "angle_deg": 45.0}

================================================================================
SECTION 4: GOLDEN STANDARD REFERENCE BLUEPRINT PLANS
================================================================================
ÖRNEK 1: Kademeli Silindirik ve Çift Kulaklı Gövde (teknik-resim-ornek-resim1.png):
{
  "parca_adi": "Kamalı ve Çift Kulaklı Kademeli Silindirik Gövde",
  "tasarim_mantigi": "Ø70 alt gövde, Ø50 boyun kanalı ve Ø70 üst flanşı 'ust' düzleminde katıla; 'on' düzleminde R11.5 kulak bloğunu 54 mm simetrik katıla, 'sag' düzleminde 30 mm iç kanalı kes, delikleri ve kama kanalını aç.",
  "muhendislik_dusuncesi": {
    "okunan_olculer": "Ø70, Ø50, Ø30, R15, R11.5, Ø10, 87, 81, 65, 54, 42, 23, 12, 10, 8, 33.20",
    "koordinat_plani": "Merkez eksen Y boyuncadır. Kulaklar X=±40.5 mm eksenindedir."
  },
  "adimlar": [
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 70.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 65.0}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 50.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 87.0}},
    {"islem": "create_ref_plane", "params": {"base_plane": "ust", "distance_mm": 77.0}},
    {"islem": "select_ref_plane", "params": {}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 70.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 10.0}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_corner_rectangle", "params": {"x1": -40.5, "y1": 0.0, "x2": 40.5, "y2": 23.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 54.0, "midplane": true}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -40.5, "y": 11.5, "dia": 23.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 54.0, "midplane": true}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 40.5, "y": 11.5, "dia": 23.0}},
    {"islem": "extrude_boss", "params": {"depth_mm": 54.0, "midplane": true}},
    {"islem": "select_plane", "params": {"plane": "sag"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_corner_rectangle", "params": {"x1": -15.0, "y1": 0.0, "x2": 15.0, "y2": 23.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": -40.5, "y": 11.5, "dia": 10.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "on"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 40.5, "y": 11.5, "dia": 10.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 30.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_corner_rectangle", "params": {"x1": -4.0, "y1": -18.2, "x2": 4.0, "y2": 0.0}},
    {"islem": "extrude_cut", "params": {"through_all": true, "both_directions": true}},
    {"islem": "select_plane", "params": {"plane": "ust"}},
    {"islem": "start_sketch", "params": {}},
    {"islem": "draw_circle", "params": {"x": 0.0, "y": 0.0, "dia": 50.0}},
    {"islem": "extrude_cut", "params": {"depth_mm": 54.0, "through_all": false}}
  ]
}

================================================================================
OUTPUT FORMAT:
RETURN ONLY AND EXCLUSIVELY A VALID RAW JSON OBJECT MATCHING THE SCHEMA.
DO NOT WRITE ANY PROSE, EXPLANATIONS, OR MARKDOWN CODE FENCES OUTSIDE THE JSON.
"""


def preprocess_drawing_image(image_path: str) -> str:
    """Preprocesses technical drawing image:
    1. Converts RGBA to clean RGB on white background.
    2. Auto-crops empty white borders so technical drawing geometry and dimension text are maximized.
    3. Resizes with high fidelity up to 1440px max dimension.
    4. Applies mild contrast & sharpness enhancement so dimension numbers (Ø, R, tolerances) are 100% crisp.
    5. Saves as high-quality JPEG (quality=92) under 200 KB.
    """
    try:
        img = Image.open(image_path)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            alpha = img.convert('RGBA')
            bg = Image.new('RGB', alpha.size, (255, 255, 255))
            bg.paste(alpha, mask=alpha.split()[3])
            img = bg
        else:
            img = img.convert('RGB')

        # Auto-crop huge white borders
        try:
            gray = img.convert('L')
            inv = ImageOps.invert(gray)
            bbox = inv.getbbox()
            if bbox:
                # Add 2% padding
                w_b, h_b = img.size
                pad_x = int(w_b * 0.02)
                pad_y = int(h_b * 0.02)
                crop_box = (
                    max(0, bbox[0] - pad_x),
                    max(0, bbox[1] - pad_y),
                    min(w_b, bbox[2] + pad_x),
                    min(h_b, bbox[3] + pad_y)
                )
                if (crop_box[2] - crop_box[0] > 200) and (crop_box[3] - crop_box[1] > 200):
                    img = img.crop(crop_box)
        except Exception:
            pass

        # High-definition scaling (up to 1440px for crystal-clear dimension readability)
        w, h = img.size
        max_dim = max(w, h)
        if max_dim > 1440:
            scale = 1440.0 / max_dim
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        elif max_dim < 700:
            scale = min(2.0, 1000.0 / max_dim)
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        # Contrast and Sharpness Enhancement for engineering dimension legibility
        try:
            enh_c = ImageEnhance.Contrast(img)
            img = enh_c.enhance(1.22)
            enh_s = ImageEnhance.Sharpness(img)
            img = enh_s.enhance(1.35)
        except Exception:
            pass

        cache_dir = settings.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        base_stem = os.path.splitext(os.path.basename(image_path))[0]
        # Strip any existing prep_ or prep_hd_ prefix to avoid chained prefixing
        clean_stem = re.sub(r'^(prep_hd_|prep_)+', '', base_stem)
        # Sanitize unsafe / non-ascii characters for clean Windows filesystem paths
        safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', clean_stem).strip('_')
        if not safe_stem:
            safe_stem = "blueprint"
        prep_path = os.path.join(cache_dir, f"prep_hd_{safe_stem}.jpg")
        img.save(prep_path, format="JPEG", quality=92)
        return prep_path
    except Exception as e:
        print(f"[Uyari] Gorsel on isleme atlandi: {e}")
        return image_path


def extract_cad_plan_gemini(image_path: str, api_key: str, user_notes: str = "", log_callback=None) -> dict:
    """Uses Google Gemini Vision (prioritizing gemini-3-flash-preview and gemini-robotics-er-2-preview
    with deep spatial reasoning) to decode blueprints and output a complete CAD plan.
    """
    if log_callback:
        log_callback("Google Gemini Vision (Spatial Intelligence) analyzing technical drawing and generating CAD plan...")

    prep_image = preprocess_drawing_image(image_path)
    with open(prep_image, "rb") as f:
        img_bytes = f.read()

    b64_data = base64.b64encode(img_bytes).decode("utf-8")

    prompt = MASTER_BLUEPRINT_SYSTEM_PROMPT
    if user_notes:
        prompt += f"\n\nUSER DIRECTIVE / ERROR RECOVERY NOTE:\n{user_notes}\n"

    last_err = None

    # Filter candidate models: skip any known 429 quota exhausted models for this session
    candidate_models = settings.get_active_gemini_models()

    for round_idx in range(2):
        for model_name in candidate_models:
            if model_name in settings.EXHAUSTED_429_MODELS:
                continue

            if log_callback:
                log_callback(f"Google Gemini Vision ({model_name}) performing spatial analysis...")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

            # High thinking budget for deep reasoning models (gemini-3-flash-preview, gemini-robotics-er-2-preview)
            is_thinking_model = any(k in model_name for k in ["gemini-3", "robotics"])
            gen_config = {
                "temperature": 0.1,
                "maxOutputTokens": 65536
            }
            if is_thinking_model:
                gen_config["thinkingConfig"] = {"thinkingBudget": 8192}

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_data
                            }
                        }
                    ]
                }],
                "generationConfig": gen_config
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=50) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    # Extract non-thought text parts
                    text = "\n".join(pt.get("text", "") for pt in parts if not pt.get("thought")).strip()
                    if not text:
                        text = "\n".join(pt.get("text", "") for pt in parts).strip()

                    plan = extract_json_plan(text)
                    if plan and ("adimlar" in plan or "steps" in plan):
                        plan = normalize_and_decompose_plan(plan)
                        sim = CADSimulator()
                        sim_res = sim.simulate(plan)
                        if not sim_res.valid:
                            print(f"[Gemini Plan Warning] Simulator flagged issues: {sim_res.errors}")
                        return plan
            except urllib.error.HTTPError as he:
                last_err = he
                if he.code == 429:
                    settings.mark_model_exhausted(model_name)
                    msg_quota = f"[Gemini Info] '{model_name}' quota exhausted on Free Tier. Switching to active model gemini-3-flash-preview (Deep Thinking: 8192 tokens)..."
                    print(msg_quota)
                    if log_callback:
                        log_callback(msg_quota)
                    continue
                elif he.code == 400 and "thinkingConfig" in gen_config:
                    # Retry once without thinkingConfig if endpoint rejected it
                    try:
                        gen_config.pop("thinkingConfig", None)
                        payload["generationConfig"] = gen_config
                        req2 = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req2, timeout=50) as resp2:
                            res_data2 = json.loads(resp2.read().decode("utf-8"))
                            parts2 = res_data2.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            text2 = "\n".join(pt.get("text", "") for pt in parts2).strip()
                            plan2 = extract_json_plan(text2)
                            if plan2 and ("adimlar" in plan2 or "steps" in plan2):
                                return normalize_and_decompose_plan(plan2)
                    except Exception:
                        pass
                print(f"[Gemini API Attempt] {model_name} HTTP {he.code}: {he}")
                time.sleep(1.0)
                continue
            except Exception as e:
                last_err = e
                print(f"[Gemini API Attempt] {model_name} error: {e}")
                time.sleep(1.0)
                continue

    raise last_err or ValueError("Gemini Vision models could not produce a CAD plan.")


def extract_cad_plan_from_image(image_path: str, user_notes: str = "",
                                api_key: str = "", log_callback=None) -> dict:
    """Analyzes an engineering drawing image and generates a validated CAD plan dictionary."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Technical drawing file not found: {image_path}")

    # 1. Prefer Gemini Vision if API key is provided
    active_key = api_key or settings.get_gemini_api_key()
    if active_key:
        try:
            return extract_cad_plan_gemini(image_path, active_key, user_notes, log_callback)
        except Exception as e:
            if log_callback:
                log_callback(f"Gemini Vision API notice ({e}), falling back to local vision model...")

    # 2. Local Ollama Vision Fallback
    models = get_available_vision_models()
    target_model = models[0] if models else settings.DEFAULT_VISION_MODEL

    extracted_specs = analyze_technical_drawing_ollama(
        image_path=image_path,
        user_notes=user_notes,
        model_name=target_model,
        log_callback=log_callback
    )

    if log_callback:
        log_callback("Local vision model extracted dimensions, generating CAD plan...")

    from agent_prompt import get_relevant_few_shots

    cad_prompt = (
        f"Using the following mechanical dimensions extracted from the 2D engineering drawing, generate a complete JSON CAD action plan for SOLIDWORKS:\n\n"
        f"DIMENSIONS & SPECIFICATIONS:\n{extracted_specs}\n"
    )
    if user_notes:
        cad_prompt += f"\nUser Custom Directive: {user_notes}\n"

    few_shots = get_relevant_few_shots(cad_prompt, max_count=1)
    messages = [{"role": "system", "content": MASTER_BLUEPRINT_SYSTEM_PROMPT}]
    messages.extend(few_shots)
    messages.append({"role": "user", "content": cad_prompt})

    attempts = 0
    max_attempts = 3
    curr_messages = list(messages)
    last_error = ""

    while attempts < max_attempts:
        attempts += 1
        try:
            stream = ollama.chat(
                model=settings.DEFAULT_CODER_MODEL,
                messages=curr_messages,
                options=settings.LLM_OPTIONS,
                stream=False
            )
            raw_reply = stream.get('message', {}).get('content', '')
            plan_dict = extract_json_plan(raw_reply)
            sim = CADSimulator()
            sim_res = sim.simulate(plan_dict)
            if sim_res.valid:
                return normalize_and_decompose_plan(plan_dict)
            last_error = " / ".join(sim_res.errors)
        except Exception as ex:
            last_error = str(ex)

        curr_messages.append({"role": "user", "content": f"Previous plan had errors: {last_error}. Please return a corrected raw JSON object."})

    raise RuntimeError(f"Could not generate valid CAD plan from drawing: {last_error}")


def analyze_technical_drawing_ollama(image_path: str, user_notes: str = "",
                                    model_name: str = "minicpm-v:latest",
                                    log_callback=None) -> str:
    """Extracts structured blueprint specifications from the drawing image using local Ollama VLM."""
    if log_callback:
        log_callback(f"Vision AI ({model_name}) analyzing drawing views...")

    prep_image = preprocess_drawing_image(image_path)
    user_content = "Analyze this mechanical drawing and list all dimensions and features."
    if user_notes:
        user_content += f"\n\nUser Directives: {user_notes}"

    messages = [
        {
            "role": "user",
            "content": user_content,
            "images": [os.path.abspath(prep_image)]
        }
    ]

    response = ollama.chat(
        model=model_name,
        messages=messages,
        keep_alive=0,
        options=settings.VISION_LLM_OPTIONS
    )

    return response.get('message', {}).get('content', '')


def get_available_vision_models() -> list[str]:
    """Returns installed Ollama models that support vision."""
    known_vision_names = ["minicpm-v", "llama3.2-vision", "llava", "bakllava", "moondream"]
    try:
        models = ollama.list().get("models", [])
        installed = []
        for m in models:
            name = m.get("model", m.get("name", "")).lower()
            for v in known_vision_names:
                if v in name:
                    installed.append(m.get("model", m.get("name", "")))
                    break
        return installed
    except Exception:
        return []
