"""
SolidAI — Central Settings & Configuration Module
Manages model names, Ollama runtime parameters, Gemini API credentials, and file paths.
"""
import os
import json

# Project Root Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Config & Cache Paths
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CACHE_DIR = os.path.join(BASE_DIR, ".solidai_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# LLM & VLM Defaults (Optimized for 8 GB VRAM RTX 4060 Laptop GPU)
DEFAULT_CODER_MODEL = "qwen2.5-coder:7b"
DEFAULT_VISION_MODEL = "minicpm-v:latest"

LLM_OPTIONS = {
    "temperature": 0.1,
    "repeat_penalty": 1.02,  # Low penalty to prevent corrupting JSON syntax
    "num_predict": 3000,
    "num_ctx": 8192
}

VISION_LLM_OPTIONS = {
    "temperature": 0.1,
    "repeat_penalty": 1.05,
    "num_predict": 1200,
    "num_ctx": 4096
}

# Supported High-Precision Gemini Frontier Models in Priority Order
# (All 'lite' models and gemini-3.1-flash are strictly excluded)
GEMINI_CANDIDATE_MODELS = [
    "gemini-4-argon",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-robotics-er-2-preview",
    "gemini-3.8-flash",
    "gemini-3.7-flash"
]

# Session-wide in-memory cache of models that returned HTTP 429 quota exhaustion
EXHAUSTED_429_MODELS = set()


def mark_model_exhausted(model_name: str):
    """Marks a model as quota-exhausted for the current application session."""
    EXHAUSTED_429_MODELS.add(model_name)


def get_active_gemini_models() -> list:
    """Returns candidate models excluding those known to be 429 exhausted in this session."""
    active = [m for m in GEMINI_CANDIDATE_MODELS if m not in EXHAUSTED_429_MODELS]
    return active if active else list(GEMINI_CANDIDATE_MODELS)


def get_gemini_api_key() -> str:
    """Retrieves Gemini API key with priority:
    1. GEMINI_API_KEY environment variable
    2. config.json file
    """
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("gemini_api_key", "").strip()
        except Exception:
            pass
    return ""


def save_gemini_api_key(key: str) -> bool:
    """Saves Gemini API key to config.json."""
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data["gemini_api_key"] = key.strip()
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"[Settings] Error saving config.json: {e}")
        return False
