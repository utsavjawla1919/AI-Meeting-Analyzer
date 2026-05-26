"""
ai_pipeline — Central AI/NLP processing package.

Exports a single `run_full_pipeline()` function that orchestrates:
  Stage 1 → Speech-to-Text      (Whisper)
  Stage 2 → Speaker Diarization (pyannote, optional)
  Stage 3 → NLP Processing      (spaCy + NLTK + TF-IDF)
  Stage 4 → Summarization       (HuggingFace BART/T5)
  Stage 5 → Action/Decision     (rule-based extraction)
  Stage 6 → Keyword/Topic       (TF-IDF + seed clustering)
  Stage 7 → Sentiment Analysis  (DistilBERT + VADER fallback)

Model Registry
--------------
Heavy models (Whisper, HuggingFace pipelines) are loaded lazily and
cached in the module-level `MODEL_REGISTRY` dict so they are shared
across pipeline runs without repeated disk I/O.
"""

import logging
import threading

logger = logging.getLogger(__name__)

# Thread-safe model registry — maps model_key → loaded model object
MODEL_REGISTRY: dict = {}
_registry_lock = threading.Lock()


def get_cached_model(key: str, loader_fn):
    """
    Return a cached model or load it with `loader_fn()` if not yet cached.
    Thread-safe via a module-level lock.
    """
    if key not in MODEL_REGISTRY:
        with _registry_lock:
            # Double-checked locking
            if key not in MODEL_REGISTRY:
                logger.info(f"[ModelRegistry] Loading model: {key}")
                MODEL_REGISTRY[key] = loader_fn()
                logger.info(f"[ModelRegistry] Loaded:  {key}")
    return MODEL_REGISTRY[key]


def clear_model_cache(key: str = None):
    """Evict one model or all models from cache (useful for memory management)."""
    with _registry_lock:
        if key:
            MODEL_REGISTRY.pop(key, None)
            logger.info(f"[ModelRegistry] Evicted: {key}")
        else:
            MODEL_REGISTRY.clear()
            logger.info("[ModelRegistry] Cache cleared")
