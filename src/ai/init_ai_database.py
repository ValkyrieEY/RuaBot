"""Initialize AI Learning Database.

This module provides automatic initialization of ai_learning.db database.
It will be called automatically on system startup.
"""

import os
from pathlib import Path

from ..core.logger import get_logger
from .ai_database import AIDatabase

logger = get_logger(__name__)


def init_ai_learning_database(db_path: str = "data/ai_learning.db") -> bool:
    """Initialize AI learning database.
    
    Args:
        db_path: Path to database file
        
    Returns:
        True if initialized successfully
    """
    try:
        # Check if database already exists
        if os.path.exists(db_path):
            logger.info(f"AI learning database already exists at: {db_path}")
            # Verify it's accessible
            ai_db = AIDatabase(db_path=db_path)
            ai_db.initialize()
            ai_db.close()
            logger.info("AI learning database verified and ready")
            return True
        
        logger.info(f"Creating AI learning database at: {db_path}")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create database instance
        ai_db = AIDatabase(db_path=db_path)
        
        # Initialize (this will create all tables)
        ai_db.initialize()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(ai_db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'ai_expressions',
            'ai_jargons',
            'ai_chat_history',
            'ai_message_records',
            'ai_person_info',
            'ai_group_info'
        ]
        
        all_present = all(table in tables for table in expected_tables)
        
        if not all_present:
            missing = [t for t in expected_tables if t not in tables]
            logger.error(f"Failed to create tables: {missing}")
            ai_db.close()
            return False
        
        # Close connection
        ai_db.close()
        
        logger.info(f"AI learning database created successfully with {len(tables)} tables")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize AI learning database: {e}", exc_info=True)
        return False


def ensure_ai_database_initialized() -> bool:
    """Ensure AI database is initialized (called on system startup).
    
    Returns:
        True if database is ready
    """
    return init_ai_learning_database()

