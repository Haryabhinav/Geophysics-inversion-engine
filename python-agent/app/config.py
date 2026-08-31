"""Runtime configuration, sourced from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    gemini_max_tokens: int = int(os.getenv("GEMINI_MAX_TOKENS", "2500"))

    # "auto"   -> use the LLM if GEMINI_API_KEY is set, else the offline modeler
    # "llm"    -> force the Gemini modeler (errors if no key)
    # "offline"-> force the deterministic pattern-search modeler
    agent_mode: str = os.getenv("AGENT_MODE", "auto")

    # Same "auto | llm | offline" selection, for the Interpretation Agent
    # (app/agent/interpreter.py). Independent of agent_mode so the inversion
    # solver and the interpreter can be toggled separately.
    interpreter_mode: str = os.getenv("INTERPRETER_MODE", "auto")

    # Same "auto | llm | offline" shape, for the LITHOLOGY classifier
    # (app/agent/classifier_modeler.py) — but defaults to "offline", not
    # "auto": lithology-from-logs is a well-benchmarked supervised problem a
    # correctly-configured Random Forest already solves well, so the
    # classical baseline is the recommended PRODUCTION default even when a
    # Gemini key is present, mirroring the lesson TDEM's own live testing
    # taught. Set CLASSIFIER_MODE=llm explicitly to demo the agentic path.
    classifier_mode: str = os.getenv("CLASSIFIER_MODE", "offline")

    # Relative misfit tolerance: ||d_obs - d_pred|| / ||d_obs||  (scale-invariant).
    l2_tolerance: float = float(os.getenv("L2_TOLERANCE", "0.05"))
    # LLM ceiling: the one-shot scipy inversion converges in 1-2 calls, so a low
    # ceiling keeps API usage tiny (important on Gemini's free ~5 req/min tier).
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "6"))
    # The offline pattern-search test double needs many cheap iterations.
    offline_max_iterations: int = int(os.getenv("OFFLINE_MAX_ITERATIONS", "200"))
    # Generous enough for the model's in-script scipy fit (many empymod evals).
    sandbox_timeout_s: int = int(os.getenv("SANDBOX_TIMEOUT_S", "20"))
    # If set, model code runs in the remote sandbox service instead of locally.
    sandbox_url: str = os.getenv("SANDBOX_URL", "")


settings = Settings()
