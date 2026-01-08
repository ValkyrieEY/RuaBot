"""Knowledge Graph System - Complete implementation.

Complete knowledge graph system inspired by RuaBot's KG module.
Features:
1. Information extraction from conversations
2. Knowledge triple storage (subject-predicate-object)
3. Knowledge retrieval and reasoning
4. Entity relationship management
5. Knowledge consolidation
"""

from .kg_manager import KGManager, get_kg_manager
from .open_ie import OpenIE, extract_triples, get_open_ie
from .kg_storage import KGStorage, get_kg_storage

__all__ = [
    'KGManager',
    'get_kg_manager',
    'OpenIE',
    'extract_triples',
    'get_open_ie',
    'KGStorage',
    'get_kg_storage'
]

