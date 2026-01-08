"""Knowledge Graph Storage - Complete database models and storage for knowledge triples.

Complete implementation with:
1. Knowledge triple storage (subject-predicate-object)
2. Entity management
3. Relationship tracking
4. Confidence scoring
5. Temporal tracking
6. Source attribution
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, Text, JSON, create_engine, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.core.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()


class KnowledgeTriple(Base):
    """Knowledge triple: subject-predicate-object."""
    
    __tablename__ = "kg_triples"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(500), nullable=False, index=True)
    predicate = Column(String(200), nullable=False, index=True)
    object = Column(String(500), nullable=False, index=True)
    
    # Metadata
    source_chat_id = Column(String(100), index=True)
    confidence = Column(Float, default=1.0)  # 0.0 to 1.0
    timestamp = Column(Float, nullable=False)
    
    # Context
    context = Column(Text)  # Original text where triple was extracted
    extraction_method = Column(String(50))  # 'llm', 'rule', 'manual'
    
    # Additional data
    attributes = Column(JSON)  # Additional triple attributes
    
    # Validation
    validated = Column(Integer, default=0)  # 0=unvalidated, 1=validated, -1=rejected
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_subject_predicate', 'subject', 'predicate'),
        Index('idx_predicate_object', 'predicate', 'object'),
        Index('idx_chat_timestamp', 'source_chat_id', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'subject': self.subject,
            'predicate': self.predicate,
            'object': self.object,
            'source_chat_id': self.source_chat_id,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'context': self.context,
            'extraction_method': self.extraction_method,
            'attributes': self.attributes,
            'validated': self.validated
        }


class Entity(Base):
    """Entity in the knowledge graph."""
    
    __tablename__ = "kg_entities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False, unique=True, index=True)
    entity_type = Column(String(50), index=True)  # 'person', 'place', 'thing', 'concept'
    
    # Metadata
    description = Column(Text)
    aliases = Column(JSON)  # List of alternative names
    attributes = Column(JSON)  # Entity attributes
    
    # Statistics
    mention_count = Column(Integer, default=0)
    last_mentioned = Column(Float)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'entity_type': self.entity_type,
            'description': self.description,
            'aliases': self.aliases,
            'attributes': self.attributes,
            'mention_count': self.mention_count,
            'last_mentioned': self.last_mentioned
        }


class Relationship(Base):
    """Relationship between entities."""
    
    __tablename__ = "kg_relationships"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity1_id = Column(Integer, nullable=False, index=True)
    relationship_type = Column(String(200), nullable=False, index=True)
    entity2_id = Column(Integer, nullable=False, index=True)
    
    # Metadata
    confidence = Column(Float, default=1.0)
    source_triple_ids = Column(JSON)  # List of triple IDs that support this relationship
    first_seen = Column(Float)
    last_seen = Column(Float)
    
    # Attributes
    attributes = Column(JSON)
    
    __table_args__ = (
        Index('idx_entity1_relationship', 'entity1_id', 'relationship_type'),
        Index('idx_relationship_entity2', 'relationship_type', 'entity2_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'entity1_id': self.entity1_id,
            'relationship_type': self.relationship_type,
            'entity2_id': self.entity2_id,
            'confidence': self.confidence,
            'source_triple_ids': self.source_triple_ids,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'attributes': self.attributes
        }


class KGStorage:
    """Storage manager for knowledge graph."""
    
    def __init__(self, db_path: str = "data/knowledge_graph.db"):
        """Initialize KG storage.
        
        Args:
            db_path: Path to SQLite database
        """
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"[KGStorage] 初始化完成: {db_path}")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()
    
    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        source_chat_id: Optional[str] = None,
        confidence: float = 1.0,
        timestamp: Optional[float] = None,
        context: Optional[str] = None,
        extraction_method: str = "llm",
        attributes: Optional[Dict[str, Any]] = None
    ) -> KnowledgeTriple:
        """Add a knowledge triple.
        
        Args:
            subject: Subject entity
            predicate: Predicate/relationship
            object: Object entity
            source_chat_id: Source chat ID
            confidence: Confidence score (0-1)
            timestamp: Timestamp
            context: Original context
            extraction_method: Extraction method
            attributes: Additional attributes
            
        Returns:
            Created KnowledgeTriple object
        """
        import time
        
        session = self.get_session()
        try:
            triple = KnowledgeTriple(
                subject=subject,
                predicate=predicate,
                object=object,
                source_chat_id=source_chat_id,
                confidence=confidence,
                timestamp=timestamp or time.time(),
                context=context,
                extraction_method=extraction_method,
                attributes=attributes
            )
            session.add(triple)
            session.commit()
            session.refresh(triple)
            
            logger.debug(f"[KGStorage] 添加三元组: ({subject}, {predicate}, {object})")
            return triple
        finally:
            session.close()
    
    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        source_chat_id: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100
    ) -> List[KnowledgeTriple]:
        """Query knowledge triples.
        
        Args:
            subject: Filter by subject
            predicate: Filter by predicate
            object: Filter by object
            source_chat_id: Filter by source chat
            min_confidence: Minimum confidence
            limit: Maximum results
            
        Returns:
            List of KnowledgeTriple objects
        """
        session = self.get_session()
        try:
            query = session.query(KnowledgeTriple)
            
            if subject:
                query = query.filter(KnowledgeTriple.subject == subject)
            if predicate:
                query = query.filter(KnowledgeTriple.predicate == predicate)
            if object:
                query = query.filter(KnowledgeTriple.object == object)
            if source_chat_id:
                query = query.filter(KnowledgeTriple.source_chat_id == source_chat_id)
            if min_confidence > 0:
                query = query.filter(KnowledgeTriple.confidence >= min_confidence)
            
            query = query.order_by(KnowledgeTriple.timestamp.desc())
            query = query.limit(limit)
            
            return query.all()
        finally:
            session.close()
    
    def get_or_create_entity(
        self,
        name: str,
        entity_type: Optional[str] = None,
        description: Optional[str] = None
    ) -> Entity:
        """Get or create an entity.
        
        Args:
            name: Entity name
            entity_type: Entity type
            description: Entity description
            
        Returns:
            Entity object
        """
        session = self.get_session()
        try:
            entity = session.query(Entity).filter(Entity.name == name).first()
            
            if not entity:
                entity = Entity(
                    name=name,
                    entity_type=entity_type,
                    description=description,
                    mention_count=0
                )
                session.add(entity)
                session.commit()
                session.refresh(entity)
                logger.debug(f"[KGStorage] 创建实体: {name}")
            
            return entity
        finally:
            session.close()
    
    def update_entity_mention(self, name: str, timestamp: float):
        """Update entity mention statistics.
        
        Args:
            name: Entity name
            timestamp: Mention timestamp
        """
        session = self.get_session()
        try:
            entity = session.query(Entity).filter(Entity.name == name).first()
            if entity:
                entity.mention_count += 1
                entity.last_mentioned = timestamp
                session.commit()
        finally:
            session.close()
    
    def get_entity_relationships(self, entity_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get relationships for an entity.
        
        Args:
            entity_name: Entity name
            limit: Maximum results
            
        Returns:
            List of relationship dicts
        """
        triples = self.query_triples(subject=entity_name, limit=limit)
        
        relationships = []
        for triple in triples:
            relationships.append({
                'subject': triple.subject,
                'predicate': triple.predicate,
                'object': triple.object,
                'confidence': triple.confidence,
                'timestamp': triple.timestamp
            })
        
        return relationships
    
    def search_triples_by_text(
        self,
        search_text: str,
        limit: int = 50
    ) -> List[KnowledgeTriple]:
        """Search triples by text (subject, predicate, or object contains text).
        
        Args:
            search_text: Search text
            limit: Maximum results
            
        Returns:
            List of KnowledgeTriple objects
        """
        session = self.get_session()
        try:
            search_pattern = f"%{search_text}%"
            
            query = session.query(KnowledgeTriple).filter(
                (KnowledgeTriple.subject.like(search_pattern)) |
                (KnowledgeTriple.predicate.like(search_pattern)) |
                (KnowledgeTriple.object.like(search_pattern))
            )
            
            query = query.order_by(KnowledgeTriple.confidence.desc())
            query = query.limit(limit)
            
            return query.all()
        finally:
            session.close()
    
    def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Entity]:
        """Get entities.
        
        Args:
            entity_type: Filter by entity type
            limit: Maximum results
            offset: Offset for pagination
            
        Returns:
            List of Entity objects
        """
        session = self.get_session()
        try:
            query = session.query(Entity)
            
            if entity_type:
                query = query.filter(Entity.entity_type == entity_type)
            
            query = query.order_by(Entity.mention_count.desc(), Entity.last_mentioned.desc())
            query = query.offset(offset).limit(limit)
            
            return query.all()
        finally:
            session.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics.
        
        Returns:
            Statistics dict
        """
        session = self.get_session()
        try:
            triple_count = session.query(KnowledgeTriple).count()
            entity_count = session.query(Entity).count()
            relationship_count = session.query(Relationship).count()
            
            # Calculate average confidence
            avg_confidence_result = session.query(
                func.avg(KnowledgeTriple.confidence)
            ).scalar()
            avg_confidence = float(avg_confidence_result) if avg_confidence_result else 0.0
            
            return {
                'triples': triple_count,
                'entities': entity_count,
                'relationships': relationship_count,
                'avg_confidence': avg_confidence
            }
        finally:
            session.close()


# Global instance
_kg_storage: Optional[KGStorage] = None


def get_kg_storage(db_path: str = "data/knowledge_graph.db") -> KGStorage:
    """Get global KG storage instance.
    
    Args:
        db_path: Path to database
        
    Returns:
        KGStorage instance
    """
    global _kg_storage
    if _kg_storage is None:
        _kg_storage = KGStorage(db_path)
    return _kg_storage

