"""Chess in the Hand of AI – a chess engine with four AI levels."""

from .engine import LEVELS, LEVEL_NAMES, Engine, EngineConfig, make_engine, make_variant
from .search import SearchResult, format_score

__all__ = ["LEVELS", "LEVEL_NAMES", "Engine", "EngineConfig", "make_engine", "make_variant",
           "SearchResult", "format_score"]
__version__ = "1.0.0"
