"""Local paths and model configuration. All models run through a local Ollama server."""

import os
from pathlib import Path

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEBUG = False
MAX_CHUNK_SIZE = 4
LLM_VERS = os.environ.get("LLM_MODEL", "qwen3:4b-instruct")
# Saved memories were embedded with this model; changing it requires re-embedding them.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "qwen3-embedding:0.6b")
BASE_DIR = Path(__file__).resolve().parent.parent
POPULATIONS_DIR = str(BASE_DIR / "agent_bank")
LLM_PROMPT_DIR = str(BASE_DIR / "simulation_engine" / "prompt_template")
