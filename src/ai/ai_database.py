"""AI dedicated database manager.

Manages a separate SQLite database for AI learning features, completely independent
from the main plugins.db database.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from datetime import datetime

from ..core.logger import get_logger
from .ai_database_models import Base, AI_MODELS, Expression, Jargon, ChatHistory, MessageRecord, PersonInfo, GroupInfo, Sticker

logger = get_logger(__name__)


class AIDatabase:
    """AI dedicated database manager.
    
    Handles all database operations for RuaBot-style learning features.
    Uses a separate SQLite database (ai_learning.db) from main framework database.
    """
    
    def __init__(self, db_path: str = "data/ai_learning.db"):
        """Initialize AI database.
        
        Args:
            db_path: Path to SQLite database file (default: data/ai_learning.db)
        """
        self.db_path = db_path
        self.engine = None
        self.session_factory = None
        self._initialized = False
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def initialize(self):
        """Initialize database connection and create tables."""
        if self._initialized:
            return
        
        # Create engine with connection pooling
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,  # Use StaticPool for single-file SQLite
            echo=False  # Set to True for SQL debugging
        )
        
        # Create all tables
        Base.metadata.create_all(self.engine)
        
        # Create session factory with scoped_session for thread safety
        self.session_factory = scoped_session(
            sessionmaker(bind=self.engine, expire_on_commit=False)
        )
        
        self._initialized = True
        logger.info(f"AI database initialized at {self.db_path}")
    
    def get_session(self):
        """Get a new database session.
        
        Returns:
            SQLAlchemy session object
        """
        if not self._initialized:
            self.initialize()
        return self.session_factory()
    
    def close(self):
        """Close database connection."""
        if self.session_factory:
            self.session_factory.remove()
        if self.engine:
            self.engine.dispose()
        self._initialized = False
        logger.info("AI database connection closed")
    
    # ==================== Expression Operations ====================
    
    async def get_expressions(
        self, 
        chat_id: Optional[str] = None,
        checked: Optional[bool] = None,
        rejected: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[Expression]:
        """Get expressions with optional filters.
        
        Args:
            chat_id: Filter by chat ID
            checked: Filter by checked status
            rejected: Filter by rejected status
            limit: Maximum number of results
            
        Returns:
            List of Expression objects
        """
        def _query():
            session = self.get_session()
            try:
                query = session.query(Expression)
                
                if chat_id:
                    query = query.filter(Expression.chat_id == chat_id)
                if checked is not None:
                    query = query.filter(Expression.checked == checked)
                if rejected is not None:
                    query = query.filter(Expression.rejected == rejected)
                
                query = query.order_by(desc(Expression.count), desc(Expression.last_active_time))
                
                if limit:
                    query = query.limit(limit)
                
                return query.all()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query)
    
    async def create_expression(
        self,
        situation: str,
        style: str,
        chat_id: str,
        content_list: Optional[List[str]] = None,
        **kwargs
    ) -> Expression:
        """Create a new expression record.
        
        Args:
            situation: Situation description
            style: Speaking style
            chat_id: Chat ID
            content_list: Context list
            **kwargs: Additional fields
            
        Returns:
            Created Expression object
        """
        def _create():
            session = self.get_session()
            try:
                expression = Expression(
                    situation=situation,
                    style=style,
                    chat_id=chat_id,
                    content_list=content_list,
                    **kwargs
                )
                session.add(expression)
                session.commit()
                session.refresh(expression)
                return expression
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create)
    
    async def update_expression(self, expression_id: int, **kwargs) -> bool:
        """Update an expression record.
        
        Args:
            expression_id: Expression ID
            **kwargs: Fields to update
            
        Returns:
            True if updated successfully
        """
        def _update():
            session = self.get_session()
            try:
                expression = session.query(Expression).filter(Expression.id == expression_id).first()
                if not expression:
                    return False
                
                for key, value in kwargs.items():
                    if hasattr(expression, key):
                        setattr(expression, key, value)
                
                expression.updated_at = datetime.utcnow()
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _update)
    
    async def find_similar_expression(
        self,
        chat_id: str,
        situation: str,
        style: str,
        similarity_threshold: float = 0.8
    ) -> Optional[Expression]:
        """Find similar expression (simple string matching for now).
        
        Args:
            chat_id: Chat ID
            situation: Situation to match
            style: Style to match
            similarity_threshold: Similarity threshold (not used yet)
            
        Returns:
            Similar Expression object or None
        """
        def _find():
            session = self.get_session()
            try:
                # Simple exact match for now (can be enhanced with fuzzy matching)
                expression = session.query(Expression).filter(
                    and_(
                        Expression.chat_id == chat_id,
                        Expression.situation == situation,
                        Expression.style == style
                    )
                ).first()
                return expression
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _find)
    
    # ==================== Jargon Operations ====================
    
    async def get_jargons(
        self,
        chat_id: Optional[str] = None,
        is_jargon: Optional[bool] = None,
        is_global: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[Jargon]:
        """Get jargons with optional filters.
        
        Args:
            chat_id: Filter by chat ID
            is_jargon: Filter by jargon status
            is_global: Filter by global status
            limit: Maximum number of results
            
        Returns:
            List of Jargon objects
        """
        def _query():
            session = self.get_session()
            try:
                query = session.query(Jargon)
                
                if chat_id:
                    query = query.filter(Jargon.chat_id == chat_id)
                if is_jargon is not None:
                    query = query.filter(Jargon.is_jargon == is_jargon)
                if is_global is not None:
                    query = query.filter(Jargon.is_global == is_global)
                
                query = query.order_by(desc(Jargon.count))
                
                if limit:
                    query = query.limit(limit)
                
                return query.all()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query)
    
    async def create_jargon(
        self,
        content: str,
        chat_id: str,
        raw_content: Optional[List[str]] = None,
        **kwargs
    ) -> Jargon:
        """Create a new jargon record.
        
        Args:
            content: Jargon content
            chat_id: Chat ID
            raw_content: Context list
            **kwargs: Additional fields
            
        Returns:
            Created Jargon object
        """
        def _create():
            session = self.get_session()
            try:
                jargon = Jargon(
                    content=content,
                    chat_id=chat_id,
                    raw_content=raw_content,
                    **kwargs
                )
                session.add(jargon)
                session.commit()
                session.refresh(jargon)
                return jargon
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create)
    
    async def update_jargon(self, jargon_id: int, **kwargs) -> bool:
        """Update a jargon record.
        
        Args:
            jargon_id: Jargon ID
            **kwargs: Fields to update
            
        Returns:
            True if updated successfully
        """
        def _update():
            session = self.get_session()
            try:
                jargon = session.query(Jargon).filter(Jargon.id == jargon_id).first()
                if not jargon:
                    return False
                
                for key, value in kwargs.items():
                    if hasattr(jargon, key):
                        setattr(jargon, key, value)
                
                jargon.updated_at = datetime.utcnow()
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _update)
    
    async def find_jargon_by_content(
        self,
        chat_id: str,
        content: str
    ) -> Optional[Jargon]:
        """Find jargon by content.
        
        Args:
            chat_id: Chat ID
            content: Jargon content
            
        Returns:
            Jargon object or None
        """
        def _find():
            session = self.get_session()
            try:
                jargon = session.query(Jargon).filter(
                    and_(
                        Jargon.chat_id == chat_id,
                        Jargon.content == content
                    )
                ).first()
                return jargon
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _find)
    
    # ==================== Message Record Operations ====================
    
    async def save_message_record(
        self,
        chat_id: str,
        user_id: str,
        plain_text: Optional[str] = None,
        time: Optional[float] = None,
        **kwargs
    ) -> MessageRecord:
        """Save a message record.
        
        Args:
            chat_id: Chat ID
            user_id: User ID
            plain_text: Message text
            time: Message timestamp
            **kwargs: Additional fields
            
        Returns:
            Created MessageRecord object
        """
        def _save():
            session = self.get_session()
            try:
                import time as time_module
                message_record = MessageRecord(
                    chat_id=chat_id,
                    user_id=user_id,
                    plain_text=plain_text,
                    time=time if time is not None else time_module.time(),
                    **kwargs
                )
                session.add(message_record)
                session.commit()
                session.refresh(message_record)
                return message_record
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _save)
    
    async def get_recent_messages(
        self,
        chat_id: str,
        limit: int = 50,
        exclude_bot: bool = True
    ) -> List[MessageRecord]:
        """Get recent messages for a chat.
        
        Args:
            chat_id: Chat ID
            limit: Maximum number of messages
            exclude_bot: Whether to exclude bot messages
            
        Returns:
            List of MessageRecord objects
        """
        def _query():
            session = self.get_session()
            try:
                query = session.query(MessageRecord).filter(
                    MessageRecord.chat_id == chat_id
                )
                
                if exclude_bot:
                    query = query.filter(MessageRecord.is_bot_message == False)
                
                query = query.order_by(desc(MessageRecord.time)).limit(limit)
                messages = query.all()
                
                # Return in chronological order (oldest first)
                return list(reversed(messages))
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query)
    
    # ==================== Chat History Operations ====================
    
    async def save_chat_history(
        self,
        chat_id: str,
        start_time: float,
        end_time: float,
        original_text: str,
        summary: str,
        theme: str,
        **kwargs
    ) -> ChatHistory:
        """Save a chat history record.
        
        Args:
            chat_id: Chat ID
            start_time: Start timestamp
            end_time: End timestamp
            original_text: Original chat text
            summary: Summary
            theme: Theme
            **kwargs: Additional fields
            
        Returns:
            Created ChatHistory object
        """
        def _save():
            session = self.get_session()
            try:
                chat_history = ChatHistory(
                    chat_id=chat_id,
                    start_time=start_time,
                    end_time=end_time,
                    original_text=original_text,
                    summary=summary,
                    theme=theme,
                    **kwargs
                )
                session.add(chat_history)
                session.commit()
                session.refresh(chat_history)
                return chat_history
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _save)
    
    async def search_chat_history(
        self,
        chat_id: str,
        keywords: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[ChatHistory]:
        """Search chat history.
        
        Args:
            chat_id: Chat ID
            keywords: Keywords to search
            limit: Maximum number of results
            
        Returns:
            List of ChatHistory objects
        """
        def _search():
            session = self.get_session()
            try:
                query = session.query(ChatHistory).filter(
                    ChatHistory.chat_id == chat_id
                )
                
                # Simple keyword search (can be enhanced with vector search)
                if keywords:
                    filters = []
                    for keyword in keywords:
                        filters.append(
                            or_(
                                ChatHistory.theme.like(f"%{keyword}%"),
                                ChatHistory.summary.like(f"%{keyword}%"),
                                ChatHistory.original_text.like(f"%{keyword}%")
                            )
                        )
                    query = query.filter(or_(*filters))
                
                query = query.order_by(desc(ChatHistory.end_time)).limit(limit)
                return query.all()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _search)
    
    # ==================== Person/Group Info Operations ====================
    
    async def get_or_create_person_info(
        self,
        platform: str,
        user_id: str
    ) -> PersonInfo:
        """Get or create person info.
        
        Args:
            platform: Platform name
            user_id: User ID
            
        Returns:
            PersonInfo object
        """
        def _get_or_create():
            session = self.get_session()
            try:
                person_id = f"{platform}:{user_id}"
                person = session.query(PersonInfo).filter(
                    PersonInfo.person_id == person_id
                ).first()
                
                if not person:
                    person = PersonInfo(
                        person_id=person_id,
                        platform=platform,
                        user_id=user_id
                    )
                    session.add(person)
                    session.commit()
                    session.refresh(person)
                
                return person
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_or_create)
    
    async def get_or_create_group_info(
        self,
        platform: str,
        group_id: str
    ) -> GroupInfo:
        """Get or create group info.
        
        Args:
            platform: Platform name
            group_id: Group ID
            
        Returns:
            GroupInfo object
        """
        def _get_or_create():
            session = self.get_session()
            try:
                group = session.query(GroupInfo).filter(
                    GroupInfo.group_id == group_id
                ).first()
                
                if not group:
                    group = GroupInfo(
                        group_id=group_id,
                        platform=platform
                    )
                    session.add(group)
                    session.commit()
                    session.refresh(group)
                
                return group
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_or_create)
    
    # ==================== Person Info Operations ====================
    
    async def get_person_by_id(self, person_id: str) -> Optional[PersonInfo]:
        """Get person by person_id."""
        def _get():
            session = self.get_session()
            try:
                return session.query(PersonInfo).filter(PersonInfo.person_id == person_id).first()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)
    
    async def create_person(self, **kwargs) -> PersonInfo:
        """Create a new person record."""
        def _create():
            session = self.get_session()
            try:
                person = PersonInfo(**kwargs)
                session.add(person)
                session.commit()
                session.refresh(person)
                return person
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create)
    
    async def update_person(self, person_id: int, **kwargs) -> bool:
        """Update a person record."""
        def _update():
            session = self.get_session()
            try:
                person = session.query(PersonInfo).filter(PersonInfo.id == person_id).first()
                if not person:
                    return False
                for key, value in kwargs.items():
                    if hasattr(person, key):
                        setattr(person, key, value)
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _update)
    
    # ==================== Group Info Operations ====================
    
    async def get_group_by_id(self, group_id: str) -> Optional[GroupInfo]:
        """Get group by group_id."""
        def _get():
            session = self.get_session()
            try:
                return session.query(GroupInfo).filter(GroupInfo.group_id == group_id).first()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)
    
    async def create_group(self, **kwargs) -> GroupInfo:
        """Create a new group record."""
        def _create():
            session = self.get_session()
            try:
                group = GroupInfo(**kwargs)
                session.add(group)
                session.commit()
                session.refresh(group)
                return group
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create)
    
    async def update_group(self, group_id: int, **kwargs) -> bool:
        """Update a group record."""
        def _update():
            session = self.get_session()
            try:
                group = session.query(GroupInfo).filter(GroupInfo.id == group_id).first()
                if not group:
                    return False
                for key, value in kwargs.items():
                    if hasattr(group, key):
                        setattr(group, key, value)
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _update)
    
    # ==================== Sticker Operations ====================
    
    async def get_stickers(
        self,
        chat_id: Optional[str] = None,
        checked: Optional[bool] = None,
        rejected: Optional[bool] = None,
        sticker_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Sticker]:
        """Get stickers with optional filters."""
        def _get():
            session = self.get_session()
            try:
                query = session.query(Sticker)
                
                if chat_id:
                    query = query.filter(Sticker.chat_id == chat_id)
                if checked is not None:
                    query = query.filter(Sticker.checked == checked)
                if rejected is not None:
                    query = query.filter(Sticker.rejected == rejected)
                if sticker_type:
                    query = query.filter(Sticker.sticker_type == sticker_type)
                
                query = query.filter(Sticker.rejected == False)
                query = query.order_by(desc(Sticker.count), desc(Sticker.last_active_time))
                
                if limit:
                    query = query.limit(limit)
                
                return query.all()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)
    
    async def save_sticker(
        self,
        sticker_type: str,
        situation: str,
        chat_id: str,
        sticker_id: Optional[str] = None,
        sticker_url: Optional[str] = None,
        sticker_file: Optional[str] = None,
        emotion: Optional[str] = None,
        meaning: Optional[str] = None,
        context: Optional[str] = None
    ) -> Sticker:
        """Save or update a sticker record."""
        def _save():
            session = self.get_session()
            try:
                # Try to find existing sticker by type and identifier
                query = session.query(Sticker).filter(
                    Sticker.sticker_type == sticker_type,
                    Sticker.chat_id == chat_id
                )
                
                if sticker_id:
                    query = query.filter(Sticker.sticker_id == sticker_id)
                elif sticker_file:
                    query = query.filter(Sticker.sticker_file == sticker_file)
                elif sticker_url:
                    query = query.filter(Sticker.sticker_url == sticker_url)
                
                sticker = query.first()
                
                if sticker:
                    # Update existing
                    sticker.count += 1
                    sticker.last_active_time = time.time()
                    
                    # Update context list
                    if context:
                        if not sticker.context_list:
                            sticker.context_list = []
                        if context not in sticker.context_list:
                            sticker.context_list.append(context)
                            if len(sticker.context_list) > 10:
                                sticker.context_list = sticker.context_list[-10:]
                    
                    # Update situation/emotion/meaning if provided
                    if situation:
                        sticker.situation = situation
                    if emotion:
                        sticker.emotion = emotion
                    if meaning:
                        sticker.meaning = meaning
                else:
                    # Create new
                    import time
                    sticker = Sticker(
                        sticker_type=sticker_type,
                        sticker_id=sticker_id,
                        sticker_url=sticker_url,
                        sticker_file=sticker_file,
                        situation=situation,
                        emotion=emotion,
                        meaning=meaning,
                        chat_id=chat_id,
                        context_list=[context] if context else [],
                        count=1,
                        last_active_time=time.time(),
                        create_date=time.time(),
                        checked=False,
                        rejected=False,
                        modified_by='ai'
                    )
                    session.add(sticker)
                
                session.commit()
                session.refresh(sticker)
                return sticker
            finally:
                session.close()
        
        import time
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _save)
    
    async def get_stickers_by_situation(
        self,
        chat_id: str,
        situation: Optional[str] = None,
        emotion: Optional[str] = None,
        limit: int = 5
    ) -> List[Sticker]:
        """Get stickers matching a situation or emotion."""
        def _get():
            session = self.get_session()
            try:
                query = session.query(Sticker).filter(
                    Sticker.chat_id == chat_id,
                    Sticker.rejected == False
                )
                
                if situation:
                    query = query.filter(Sticker.situation.contains(situation))
                if emotion:
                    query = query.filter(Sticker.emotion == emotion)
                
                query = query.order_by(desc(Sticker.count), desc(Sticker.last_active_time))
                query = query.limit(limit)
                
                return query.all()
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)
    
    async def update_sticker(self, sticker_id: int, **kwargs) -> bool:
        """Update a sticker record."""
        def _update():
            session = self.get_session()
            try:
                sticker = session.query(Sticker).filter(Sticker.id == sticker_id).first()
                if not sticker:
                    return False
                for key, value in kwargs.items():
                    if hasattr(sticker, key):
                        setattr(sticker, key, value)
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _update)
    
    async def delete_sticker(self, sticker_id: int) -> bool:
        """Delete a sticker record."""
        def _delete():
            session = self.get_session()
            try:
                sticker = session.query(Sticker).filter(Sticker.id == sticker_id).first()
                if not sticker:
                    return False
                session.delete(sticker)
                session.commit()
                return True
            finally:
                session.close()
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _delete)


# Global AI database instance
_ai_db_instance: Optional[AIDatabase] = None


def get_ai_database() -> AIDatabase:
    """Get or create global AI database instance.
    
    Returns:
        AIDatabase instance
    """
    global _ai_db_instance
    if _ai_db_instance is None:
        _ai_db_instance = AIDatabase()
        _ai_db_instance.initialize()
    return _ai_db_instance


def close_ai_database():
    """Close global AI database connection."""
    global _ai_db_instance
    if _ai_db_instance is not None:
        _ai_db_instance.close()
        _ai_db_instance = None

