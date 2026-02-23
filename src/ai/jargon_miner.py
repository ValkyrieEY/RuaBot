"""Jargon Miner - learns jargon/slang from users.

Inspired by RuaBot's jargon learning system, this module:
1. Extracts potential jargon from chat messages
2. Uses dual inference mechanism to identify true jargon
3. Progressively refines meaning understanding
4. Stores and manages jargon in database
"""

import re
import json
import asyncio
from typing import List, Dict, Optional, Tuple, Any
from json_repair import repair_json

from ..core.logger import get_logger
from .ai_database import get_ai_database
from .llm_client import LLMClient

logger = get_logger(__name__)


# Inference thresholds for jargon meaning inference
INFERENCE_THRESHOLDS = [3, 6, 10, 20, 40, 60, 100]


class JargonMiner:
    """Learns and manages jargon/slang from users."""
    
    def __init__(self):
        """Initialize jargon miner."""
        self.ai_db = get_ai_database()
        self._mining_lock = asyncio.Lock()
    
    async def extract_jargons_from_messages(
        self,
        chat_id: str,
        messages: List[Dict[str, Any]],
        llm_client: Optional[LLMClient] = None,
        bot_name: str = "AI助手"
    ) -> List[Tuple[str, List[str]]]:
        """Extract potential jargons from messages.
        
        Args:
            chat_id: Chat ID
            messages: List of message dicts
            llm_client: LLM client (if None, skip extraction)
            bot_name: Bot's name (to exclude bot's own messages)
            
        Returns:
            List of (jargon_content, context_list) tuples
        """
        if not messages or not llm_client:
            return []
        
        async with self._mining_lock:
            try:
                # Build chat context
                chat_str = self._build_chat_string(messages, bot_name)
                
                # Build extraction prompt
                prompt = self._build_extraction_prompt(chat_str, bot_name)
                
                # Call LLM to extract jargons
                try:
                    response = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=1500,
                        stream=False
                    )
                    
                    if isinstance(response, dict):
                        response_text = response.get("content", "")
                    else:
                        response_text = str(response)
                except Exception as e:
                    logger.error(f"Failed to call LLM for jargon extraction: {e}", exc_info=True)
                    return []
                
                # Parse response
                jargons = self._parse_jargon_response(response_text, messages)
                
                if not jargons:
                    logger.debug("No jargons extracted from response")
                    return []
                
                # Store jargons in database
                stored_count = 0
                for content, contexts in jargons:
                    try:
                        # Check if jargon exists
                        existing = await self.ai_db.find_jargon_by_content(
                            chat_id=chat_id,
                            content=content
                        )
                        
                        if existing:
                            # Update existing jargon
                            raw_content = existing.raw_content or []
                            if isinstance(raw_content, str):
                                try:
                                    raw_content = json.loads(raw_content)
                                except json.JSONDecodeError:
                                    raw_content = [raw_content] if raw_content else []
                            
                            # Add new contexts
                            raw_content.extend(contexts)
                            # Keep only last 50 contexts
                            raw_content = raw_content[-50:]
                            
                            await self.ai_db.update_jargon(
                                existing.id,
                                raw_content=raw_content,
                                count=existing.count + len(contexts)
                            )
                            
                            # Check if need inference
                            if self._should_infer_meaning(existing.count + len(contexts), existing.last_inference_count):
                                # Trigger inference asynchronously
                                asyncio.create_task(self.infer_jargon_meaning(
                                    existing.id,
                                    llm_client
                                ))
                            
                            logger.debug(f"Updated existing jargon: {content}")
                        else:
                            # Create new jargon
                            jargon = await self.ai_db.create_jargon(
                                content=content,
                                chat_id=chat_id,
                                raw_content=contexts,
                                count=len(contexts)
                            )
                            
                            # Check if need inference (for count >= 3)
                            if len(contexts) >= 3:
                                asyncio.create_task(self.infer_jargon_meaning(
                                    jargon.id,
                                    llm_client
                                ))
                            
                            logger.debug(f"Created new jargon: {content}")
                        
                        stored_count += 1
                    except Exception as e:
                        logger.error(f"Failed to store jargon: {e}", exc_info=True)
                
                logger.info(f"Extracted and stored {stored_count}/{len(jargons)} jargons for {chat_id}")
                return jargons
                
            except Exception as e:
                logger.error(f"Failed to extract jargons: {e}", exc_info=True)
                return []
    
    def _build_chat_string(
        self,
        messages: List[Dict[str, Any]],
        bot_name: str
    ) -> str:
        """Build chat context string from messages."""
        lines = []
        for msg in messages:
            user_name = msg.get('user_name', msg.get('user_nickname', 'User'))
            content = msg.get('content', '')
            
            if not content.strip():
                continue
            
            # Replace bot's name with SELF
            if user_name == bot_name:
                user_name = "SELF"
            
            lines.append(f"{user_name}: {content}")
        
        return "\n".join(lines)
    
    def _build_extraction_prompt(self, chat_str: str, bot_name: str) -> str:
        """Build prompt for jargon extraction."""
        from .prompts import build_jargon_extraction_prompt
        return build_jargon_extraction_prompt(chat_str, bot_name)
    
    def _parse_jargon_response(
        self,
        response_text: str,
        messages: List[Dict[str, Any]]
    ) -> List[Tuple[str, List[str]]]:
        """Parse LLM response to extract jargons.
        
        Returns:
            List of (content, contexts) tuples
        """
        try:
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if not json_match:
                logger.warning("No JSON array found in jargon extraction response")
                return []
            
            json_str = json_match.group(0)
            
            # Try to parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON, trying json_repair")
                data = json.loads(repair_json(json_str))
            
            if not isinstance(data, list):
                logger.warning("Parsed data is not a list")
                return []
            
            jargons = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                content = item.get('content', '').strip()
                
                if not content or len(content) < 2 or len(content) > 15:
                    continue
                
                # Skip if contains SELF
                if 'SELF' in content:
                    continue
                
                # Build context for this jargon
                contexts = []
                for msg in messages:
                    msg_text = msg.get('content', '')
                    if content in msg_text:
                        # Build context paragraph
                        user_name = msg.get('user_name', 'User')
                        contexts.append(f"{user_name}: {msg_text}")
                
                if contexts:
                    jargons.append((content, contexts[:5]))  # Keep max 5 contexts per extraction
            
            return jargons
            
        except Exception as e:
            logger.error(f"Failed to parse jargon response: {e}", exc_info=True)
            return []
    
    def _should_infer_meaning(self, count: int, last_inference_count: Optional[int]) -> bool:
        """Check if should infer meaning based on count thresholds."""
        if count < INFERENCE_THRESHOLDS[0]:
            return False
        
        last_count = last_inference_count or 0
        
        if count <= last_count:
            return False
        
        # Find next threshold
        for threshold in INFERENCE_THRESHOLDS:
            if threshold > last_count and count >= threshold:
                return True
        
        return False
    
    async def infer_jargon_meaning(
        self,
        jargon_id: int,
        llm_client: LLMClient
    ):
        """Infer jargon meaning using dual inference mechanism.
        
        Args:
            jargon_id: Jargon database ID
            llm_client: LLM client
        """
        try:
            # Get jargon from database
            from .ai_database_models import Jargon
            session = self.ai_db.get_session()
            try:
                jargon = session.query(Jargon).filter(Jargon.id == jargon_id).first()
                if not jargon:
                    logger.warning(f"Jargon {jargon_id} not found")
                    return
                
                # Check if already complete
                if jargon.is_complete:
                    logger.debug(f"Jargon {jargon.content} inference already complete")
                    return
                
                content = jargon.content
                raw_content = jargon.raw_content or []
                if isinstance(raw_content, str):
                    try:
                        raw_content = json.loads(raw_content)
                    except json.JSONDecodeError:
                        raw_content = [raw_content] if raw_content else []
                
                if not raw_content:
                    logger.warning(f"Jargon {content} has no context for inference")
                    return
                
                # Dual inference
                # 1. Inference with context
                from .prompts import build_jargon_inference_prompt_with_context
                context_text = "\n".join(raw_content[:10])  # Use up to 10 contexts
                prompt1 = build_jargon_inference_prompt_with_context(content, context_text)
                
                response1 = await llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt1}],
                    temperature=0.3,
                    max_tokens=500,
                    stream=False
                )
                
                if isinstance(response1, dict):
                    response1_text = response1.get("content", "")
                else:
                    response1_text = str(response1)
                
                # Parse response1
                inference1 = self._parse_inference_response(response1_text)
                if not inference1 or inference1.get('no_info'):
                    logger.info(f"Jargon {content} inference with context failed (no info)")
                    return
                
                # 2. Inference content only
                from .prompts import build_jargon_inference_prompt_content_only
                prompt2 = build_jargon_inference_prompt_content_only(content)
                
                response2 = await llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt2}],
                    temperature=0.3,
                    max_tokens=500,
                    stream=False
                )
                
                if isinstance(response2, dict):
                    response2_text = response2.get("content", "")
                else:
                    response2_text = str(response2)
                
                inference2 = self._parse_inference_response(response2_text)
                if not inference2:
                    logger.info(f"Jargon {content} inference content only failed")
                    return
                
                # 3. Compare inferences
                from .prompts import build_jargon_inference_comparison_prompt
                prompt3 = build_jargon_inference_comparison_prompt(
                    inference1.get('meaning', ''),
                    inference2.get('meaning', '')
                )
                
                response3 = await llm_client.chat_completion(
                    messages=[{"role": "user", "content": prompt3}],
                    temperature=0.3,
                    max_tokens=300,
                    stream=False
                )
                
                if isinstance(response3, dict):
                    response3_text = response3.get("content", "")
                else:
                    response3_text = str(response3)
                
                comparison = self._parse_inference_response(response3_text)
                if not comparison:
                    logger.info(f"Jargon {content} comparison failed")
                    return
                
                is_similar = comparison.get('is_similar', False)
                is_jargon = not is_similar  # If different, it's jargon
                
                # Update database
                await self.ai_db.update_jargon(
                    jargon_id,
                    meaning=inference1.get('meaning', ''),
                    is_jargon=is_jargon,
                    last_inference_count=jargon.count,
                    inference_with_context=inference1,
                    inference_content_only=inference2,
                    is_complete=(jargon.count >= INFERENCE_THRESHOLDS[-1])
                )
                
                status = "是黑话" if is_jargon else "不是黑话"
                logger.info(f"Jargon {content} inference complete: {status} - {inference1.get('meaning', '')[:50]}")
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to infer jargon meaning: {e}", exc_info=True)
    
    def _parse_inference_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse inference response JSON."""
        try:
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return None
            
            json_str = json_match.group(0)
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = json.loads(repair_json(json_str))
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to parse inference response: {e}")
            return None
    
    async def get_jargon_explanations(
        self,
        chat_id: str,
        current_message: str
    ) -> str:
        """Get jargon explanations for current message.
        
        Args:
            chat_id: Chat ID
            current_message: Current message text
            
        Returns:
            Formatted jargon explanations string
        """
        try:
            # Get jargons for this chat
            jargons = await self.ai_db.get_jargons(
                chat_id=chat_id,
                is_jargon=True,
                limit=100
            )
            
            if not jargons:
                return ""
            
            # Find jargons in current message
            found_jargons = []
            for jargon in jargons:
                if not jargon.meaning:
                    continue
                
                content = jargon.content
                # Check if jargon appears in message
                if content in current_message:
                    found_jargons.append(jargon)
            
            if not found_jargons:
                return ""
            
            # Build explanation string
            lines = ["以下是聊天中出现的黑话及其含义："]
            for jargon in found_jargons[:10]:  # Max 10 jargons
                lines.append(f"- {jargon.content}: {jargon.meaning}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to get jargon explanations: {e}", exc_info=True)
            return ""


# Global jargon miner instance
_jargon_miner_instance: Optional[JargonMiner] = None


def get_jargon_miner() -> JargonMiner:
    """Get or create global jargon miner instance."""
    global _jargon_miner_instance
    if _jargon_miner_instance is None:
        _jargon_miner_instance = JargonMiner()
    return _jargon_miner_instance

