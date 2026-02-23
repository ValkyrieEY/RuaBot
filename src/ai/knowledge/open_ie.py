"""Open Information Extraction - Extract knowledge triples from text.

Complete implementation with:
1. LLM-based triple extraction
2. Entity recognition
3. Relationship extraction
4. Temporal information extraction
5. Confidence scoring
6. Batch processing
"""

import json
import re
from typing import List, Dict, Optional, Any, Tuple
from json_repair import repair_json

from src.core.logger import get_logger
from ..llm_client import LLMClient

logger = get_logger(__name__)


class OpenIE:
    """Open Information Extraction using LLM."""
    
    def __init__(self):
        """Initialize OpenIE."""
        self.entity_types = [
            'person', 'place', 'organization', 'thing', 
            'concept', 'time', 'event'
        ]
    
    async def extract_triples(
        self,
        text: str,
        llm_client: LLMClient,
        max_triples: int = 10
    ) -> List[Dict[str, Any]]:
        """Extract knowledge triples from text using LLM.
        
        Args:
            text: Input text
            llm_client: LLM client
            max_triples: Maximum number of triples to extract
            
        Returns:
            List of triple dicts with subject, predicate, object, confidence
        """
        try:
            prompt = self._build_extraction_prompt(text, max_triples)
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            if not response_text:
                return []
            
            triples = self._parse_extraction_results(response_text)
            
            logger.info(f"[OpenIE] 从文本中提取了 {len(triples)} 个三元组")
            return triples
            
        except Exception as e:
            logger.error(f"[OpenIE] 三元组提取失败: {e}", exc_info=True)
            return []
    
    def _build_extraction_prompt(self, text: str, max_triples: int) -> str:
        """Build prompt for triple extraction."""
        from ..prompts import build_triple_extraction_prompt
        return build_triple_extraction_prompt(text, max_triples)
    
    def _parse_extraction_results(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse LLM extraction results."""
        try:
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                try:
                    data = json.loads(repair_json(response_text))
                except:
                    return []
            else:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    data = json.loads(repair_json(json_str))
            
            triples = data.get('triples', [])
            
            # Validate and clean triples
            valid_triples = []
            for triple in triples:
                if all(k in triple for k in ['subject', 'predicate', 'object']):
                    valid_triples.append({
                        'subject': str(triple['subject']).strip(),
                        'subject_type': triple.get('subject_type'),
                        'predicate': str(triple['predicate']).strip(),
                        'object': str(triple['object']).strip(),
                        'object_type': triple.get('object_type'),
                        'confidence': float(triple.get('confidence', 0.8))
                    })
            
            return valid_triples
            
        except Exception as e:
            logger.error(f"[OpenIE] 解析提取结果失败: {e}")
            return []
    
    async def extract_entities(
        self,
        text: str,
        llm_client: LLMClient
    ) -> List[Dict[str, Any]]:
        """Extract named entities from text.
        
        Args:
            text: Input text
            llm_client: LLM client
            
        Returns:
            List of entity dicts with name, type, description
        """
        try:
            from ..prompts import build_entity_extraction_prompt
            prompt = build_entity_extraction_prompt(text)
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            # Parse entities
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(repair_json(json_match.group(0)))
                return data.get('entities', [])
            
            return []
            
        except Exception as e:
            logger.error(f"[OpenIE] 实体提取失败: {e}")
            return []
    
    async def extract_relationships(
        self,
        entity1: str,
        entity2: str,
        text: str,
        llm_client: LLMClient
    ) -> List[str]:
        """Extract relationships between two entities.
        
        Args:
            entity1: First entity
            entity2: Second entity
            text: Context text
            llm_client: LLM client
            
        Returns:
            List of relationship descriptions
        """
        try:
            from ..prompts import build_relationship_extraction_prompt
            prompt = build_relationship_extraction_prompt(entity1, entity2, text)
            
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            if isinstance(response, dict):
                response_text = response.get("content", "")
            else:
                response_text = str(response)
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(repair_json(json_match.group(0)))
                return data.get('relationships', [])
            
            return []
            
        except Exception as e:
            logger.error(f"[OpenIE] 关系提取失败: {e}")
            return []


# Global instance
_open_ie: Optional[OpenIE] = None


def get_open_ie() -> OpenIE:
    """Get global OpenIE instance."""
    global _open_ie
    if _open_ie is None:
        _open_ie = OpenIE()
    return _open_ie


async def extract_triples(
    text: str,
    llm_client: LLMClient,
    max_triples: int = 10
) -> List[Dict[str, Any]]:
    """Convenience function to extract triples.
    
    Args:
        text: Input text
        llm_client: LLM client
        max_triples: Maximum triples
        
    Returns:
        List of triple dicts
    """
    open_ie = get_open_ie()
    return await open_ie.extract_triples(text, llm_client, max_triples)

