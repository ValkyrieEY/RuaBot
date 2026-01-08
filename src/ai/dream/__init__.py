"""Dream System - AI Memory Maintenance.

Inspired by RuaBot's dream system, this module provides:
1. Automatic memory maintenance and organization
2. Memory consolidation and cleanup
3. ReAct-based maintenance agent
4. Scheduled dream cycles
"""

from .dream_agent import run_dream_agent_once, run_dream_cycle_once
from .dream_scheduler import start_dream_scheduler, DreamScheduler
from .dream_generator import generate_dream_summary

__all__ = [
    'run_dream_agent_once',
    'run_dream_cycle_once',
    'start_dream_scheduler',
    'DreamScheduler',
    'generate_dream_summary'
]

