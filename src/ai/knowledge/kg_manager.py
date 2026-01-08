"""Knowledge Graph Manager - Complete knowledge graph management system.

Features:
1. Knowledge extraction from conversations
2. Triple storage and retrieval
3. Entity and relationship management
4. Knowledge consolidation
5. Graph querying and reasoning
6. Statistics and monitoring
"""

import time
from typing import List, Dict, Optional, Any
from collections import defaultdict

from src.core.logger import get_logger
from ..llm_client import LLMClient
from .kg_storage import KGStorage, get_kg_storage
from .open_ie import OpenIE, get_open_ie

logger = get_logger(__name__)


class KGManager:
    """Knowledge Graph Manager."""
    
    def __init__(self, db_path: str = "data/knowledge_graph.db"):
        """Initialize KG manager.
        
        Args:
            db_path: Path to knowledge graph database
        """
        self.storage = get_kg_storage(db_path)
        self.open_ie = get_open_ie()
        
        # Statistics
        self.total_extractions = 0
        self.total_triples_extracted = 0
        self.total_entities_created = 0
        
        logger.info("[KGManager] Knowledge Graph Manager 初始化完成")
    
    async def process_message(
        self,
        text: str,
        chat_id: str,
        llm_client: LLMClient,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a message and extract knowledge.
        
        Args:
            text: Message text
            chat_id: Chat ID
            llm_client: LLM client
            user_id: User ID (optional)
            
        Returns:
            Dict with extraction results
        """
        try:
            start_time = time.time()
            
            # Extract triples
            triples = await self.open_ie.extract_triples(
                text=text,
                llm_client=llm_client,
                max_triples=5
            )
            
            if not triples:
                return {
                    'success': True,
                    'triples_extracted': 0,
                    'entities_created': 0,
                    'cost_seconds': time.time() - start_time
                }
            
            # Store triples
            stored_triples = []
            entities_created = set()
            
            for triple in triples:
                # Store triple
                stored_triple = self.storage.add_triple(
                    subject=triple['subject'],
                    predicate=triple['predicate'],
                    object=triple['object'],
                    source_chat_id=chat_id,
                    confidence=triple.get('confidence', 0.8),
                    timestamp=time.time(),
                    context=text,
                    extraction_method='llm',
                    attributes={
                        'subject_type': triple.get('subject_type'),
                        'object_type': triple.get('object_type'),
                        'user_id': user_id
                    }
                )
                stored_triples.append(stored_triple)
                
                # Create or update entities
                for entity_name, entity_type in [
                    (triple['subject'], triple.get('subject_type')),
                    (triple['object'], triple.get('object_type'))
                ]:
                    entity = self.storage.get_or_create_entity(
                        name=entity_name,
                        entity_type=entity_type
                    )
                    self.storage.update_entity_mention(entity_name, time.time())
                    entities_created.add(entity_name)
            
            # Update statistics
            self.total_extractions += 1
            self.total_triples_extracted += len(stored_triples)
            self.total_entities_created += len(entities_created)
            
            cost = time.time() - start_time
            
            logger.info(
                f"[KGManager] 处理消息: 提取 {len(stored_triples)} 个三元组, "
                f"涉及 {len(entities_created)} 个实体, 耗时 {cost:.2f}s"
            )
            
            return {
                'success': True,
                'triples_extracted': len(stored_triples),
                'entities_created': len(entities_created),
                'triples': [t.to_dict() for t in stored_triples],
                'cost_seconds': cost
            }
            
        except Exception as e:
            logger.error(f"[KGManager] 处理消息失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'triples_extracted': 0,
                'entities_created': 0
            }
    
    async def query_knowledge(
        self,
        query: str,
        llm_client: LLMClient,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Query knowledge graph using natural language.
        
        Args:
            query: Natural language query
            llm_client: LLM client
            limit: Maximum results
            
        Returns:
            List of relevant triples
        """
        try:
            # Use LLM to parse query into keywords
            prompt = f"""请从以下查询中提取关键词，用于搜索知识图谱。

查询：{query}

输出关键词列表（JSON格式）：
{{
    "keywords": ["关键词1", "关键词2", ...]
}}

只输出JSON。"""
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            # Extract keywords
            import json
            import re
            from json_repair import repair_json
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(repair_json(json_match.group(0)))
                keywords = data.get('keywords', [])
            else:
                keywords = [query]
            
            # Search for each keyword
            all_triples = []
            seen_ids = set()
            
            for keyword in keywords[:3]:  # Limit to 3 keywords
                triples = self.storage.search_triples_by_text(
                    search_text=keyword,
                    limit=limit
                )
                
                for triple in triples:
                    if triple.id not in seen_ids:
                        all_triples.append(triple.to_dict())
                        seen_ids.add(triple.id)
            
            logger.info(f"[KGManager] 查询'{query}'返回 {len(all_triples)} 个结果")
            
            return all_triples[:limit]
            
        except Exception as e:
            logger.error(f"[KGManager] 查询失败: {e}", exc_info=True)
            return []
    
    def get_entity_knowledge(
        self,
        entity_name: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get all knowledge about an entity.
        
        Args:
            entity_name: Entity name
            limit: Maximum relationships
            
        Returns:
            Dict with entity info and relationships
        """
        try:
            # Get relationships
            relationships = self.storage.get_entity_relationships(
                entity_name=entity_name,
                limit=limit
            )
            
            # Group by predicate
            grouped = defaultdict(list)
            for rel in relationships:
                grouped[rel['predicate']].append(rel['object'])
            
            return {
                'entity': entity_name,
                'relationship_count': len(relationships),
                'relationships': relationships,
                'grouped_relationships': dict(grouped)
            }
            
        except Exception as e:
            logger.error(f"[KGManager] 获取实体知识失败: {e}")
            return {
                'entity': entity_name,
                'relationship_count': 0,
                'relationships': [],
                'grouped_relationships': {}
            }
    
    def consolidate_knowledge(
        self,
        entity_name: str,
        merge_similar: bool = True
    ) -> Dict[str, Any]:
        """Consolidate knowledge about an entity.
        
        Args:
            entity_name: Entity name
            merge_similar: Whether to merge similar relationships
            
        Returns:
            Consolidation results
        """
        try:
            # Get all triples about this entity
            triples = self.storage.query_triples(
                subject=entity_name,
                limit=1000
            )
            
            if not triples:
                return {
                    'entity': entity_name,
                    'consolidated': 0,
                    'removed_duplicates': 0
                }
            
            # Group by predicate-object pairs
            unique_pairs = {}
            duplicates = []
            
            for triple in triples:
                key = (triple.predicate, triple.object)
                if key in unique_pairs:
                    # Duplicate found
                    existing = unique_pairs[key]
                    # Keep the one with higher confidence
                    if triple.confidence > existing.confidence:
                        duplicates.append(existing.id)
                        unique_pairs[key] = triple
                    else:
                        duplicates.append(triple.id)
                else:
                    unique_pairs[key] = triple
            
            logger.info(
                f"[KGManager] 整理实体 '{entity_name}': "
                f"{len(triples)} 个三元组, 发现 {len(duplicates)} 个重复"
            )
            
            # TODO: Actually remove duplicates from database
            # For now just return statistics
            
            return {
                'entity': entity_name,
                'total_triples': len(triples),
                'unique_triples': len(unique_pairs),
                'duplicates_found': len(duplicates),
                'consolidated': len(duplicates)
            }
            
        except Exception as e:
            logger.error(f"[KGManager] 整理知识失败: {e}")
            return {
                'entity': entity_name,
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics.
        
        Returns:
            Statistics dict
        """
        try:
            storage_stats = self.storage.get_statistics()
            
            return {
                **storage_stats,
                'total_extractions': self.total_extractions,
                'total_triples_extracted': self.total_triples_extracted,
                'total_entities_created': self.total_entities_created,
                'avg_triples_per_extraction': (
                    self.total_triples_extracted / self.total_extractions
                    if self.total_extractions > 0 else 0
                )
            }
        except Exception as e:
            logger.error(f"[KGManager] 获取统计失败: {e}")
            return {
                'triples': 0,
                'entities': 0,
                'relationships': 0
            }


# Global instance
_kg_manager: Optional[KGManager] = None


def get_kg_manager(db_path: str = "data/knowledge_graph.db") -> KGManager:
    """Get global KG manager instance.
    
    Args:
        db_path: Path to database
        
    Returns:
        KGManager instance
    """
    global _kg_manager
    if _kg_manager is None:
        _kg_manager = KGManager(db_path)
    return _kg_manager

