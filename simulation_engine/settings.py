"""Local paths and model configuration for the assignment."""

import os
from pathlib import Path

MODEL_BACKEND = os.environ.get("MODEL_BACKEND", "openai").lower()
if MODEL_BACKEND not in {"openai", "ollama"}:
    raise ValueError("MODEL_BACKEND must be 'openai' or 'ollama'")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if MODEL_BACKEND == "openai" and not OPENAI_API_KEY:
    try:
        from simulation_engine.setting import OPENAI_API_KEY
    except ModuleNotFoundError:
        pass

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEBUG = False
MAX_CHUNK_SIZE = 4
LLM_VERS = os.environ.get(
    "LLM_MODEL", "qwen3:4b-instruct" if MODEL_BACKEND == "ollama" else "gpt-4o-mini"
)
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "qwen3-embedding:0.6b" if MODEL_BACKEND == "ollama" else "text-embedding-3-small",
)
BASE_DIR = Path(__file__).resolve().parent.parent
POPULATIONS_DIR = str(BASE_DIR / "agent_bank" / "populations")
LLM_PROMPT_DIR = str(BASE_DIR / "simulation_engine" / "prompt_template")
