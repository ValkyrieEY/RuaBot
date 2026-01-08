"""Dream Agent - ReAct-based memory maintenance agent.

Inspired by RuaBot's dream system, this agent:
1. Uses ReAct (Reasoning-Acting-Observing) pattern
2. Automatically maintains and organizes memories
3. Consolidates redundant memories
4. Rewrites unclear summaries
5. Deletes useless records
"""

import asyncio
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from src.core.logger import get_logger
from ..llm_client import LLMClient
from ..ai_database import get_ai_database
from ..ai_database_models import ChatHistory

# Dream tools
from .tools import (
    make_search_chat_history,
    make_get_chat_history_detail,
    make_create_chat_history,
    make_update_chat_history,
    make_delete_chat_history,
    make_search_jargon,
    make_finish_maintenance
)

logger = get_logger(__name__)


class DreamTool:
    """Simple tool wrapper for dream agent."""
    
    def __init__(self, name: str, description: str, parameters: List[Tuple], execute_func):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute_func = execute_func
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p[0],
                    "type": p[1],
                    "description": p[2],
                    "required": p[3] if len(p) > 3 else False
                }
                for p in self.parameters
            ]
        }
    
    async def execute(self, **kwargs) -> str:
        return await self.execute_func(**kwargs)


class DreamToolRegistry:
    """Registry for dream tools."""
    
    def __init__(self):
        self.tools: Dict[str, DreamTool] = {}
    
    def register_tool(self, tool: DreamTool):
        self.tools[tool.name] = tool
        logger.debug(f"[Dream] 注册工具: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[DreamTool]:
        return self.tools.get(name)
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [tool.get_tool_definition() for tool in self.tools.values()]


def _init_dream_tools(chat_id: str) -> DreamToolRegistry:
    """Initialize dream tools for a specific chat_id."""
    registry = DreamToolRegistry()
    
    # Create tool functions
    search_chat_history = make_search_chat_history(chat_id)
    get_chat_history_detail = make_get_chat_history_detail(chat_id)
    create_chat_history = make_create_chat_history(chat_id)
    update_chat_history = make_update_chat_history(chat_id)
    delete_chat_history = make_delete_chat_history(chat_id)
    search_jargon = make_search_jargon(chat_id)
    finish_maintenance = make_finish_maintenance(chat_id)
    
    # Register tools
    registry.register_tool(DreamTool(
        "search_chat_history",
        "根据关键词或参与人查询当前 chat_id 下的 ChatHistory 概览",
        [
            ("keyword", "string", "关键词（可选，支持多个关键词，可用空格、逗号等分隔）", False),
            ("participant", "string", "参与人昵称（可选）", False),
        ],
        search_chat_history
    ))
    
    registry.register_tool(DreamTool(
        "get_chat_history_detail",
        "根据 memory_id 获取单条 ChatHistory 的详细内容",
        [
            ("memory_id", "integer", "ChatHistory 主键 ID", True),
        ],
        get_chat_history_detail
    ))
    
    registry.register_tool(DreamTool(
        "create_chat_history",
        "创建一条新的 ChatHistory 概括记录",
        [
            ("theme", "string", "主题标题（必填）", True),
            ("summary", "string", "概括内容（必填）", True),
            ("keywords", "string", "关键词 JSON 字符串，如 ['关键词1','关键词2']（必填）", True),
            ("key_point", "string", "关键信息 JSON 字符串，如 ['要点1','要点2']（必填）", True),
            ("start_time", "string", "起始时间戳（秒，Unix 时间，必填）", True),
            ("end_time", "string", "结束时间戳（秒，Unix 时间，必填）", True),
        ],
        create_chat_history
    ))
    
    registry.register_tool(DreamTool(
        "update_chat_history",
        "更新 ChatHistory 记录的字段",
        [
            ("memory_id", "integer", "需要更新的 ChatHistory 主键 ID", True),
            ("theme", "string", "新的主题标题（可选）", False),
            ("summary", "string", "新的概括内容（可选）", False),
            ("keywords", "string", "新的关键词 JSON 字符串（可选）", False),
            ("key_point", "string", "新的关键信息 JSON 字符串（可选）", False),
        ],
        update_chat_history
    ))
    
    registry.register_tool(DreamTool(
        "delete_chat_history",
        "删除一条 ChatHistory 记录（请谨慎使用）",
        [
            ("memory_id", "integer", "需要删除的 ChatHistory 主键 ID", True),
        ],
        delete_chat_history
    ))
    
    registry.register_tool(DreamTool(
        "search_jargon",
        "搜索当前 chat_id 相关的 Jargon（黑话）记录（只读）",
        [
            ("keyword", "string", "关键词（必填）", True),
        ],
        search_jargon
    ))
    
    registry.register_tool(DreamTool(
        "finish_maintenance",
        "结束本次 dream 维护任务",
        [
            ("reason", "string", "结束维护的原因说明（可选）", False),
        ],
        finish_maintenance
    ))
    
    return registry


def _build_dream_prompt(
    chat_id: str,
    bot_name: str,
    start_memory_id: Optional[int],
    max_iterations: int
) -> str:
    """Build the dream agent prompt."""
    return f"""你的名字是{bot_name}，你现在处于"梦境维护模式（dream agent）"。
你可以自由地在 ChatHistory 库中探索、整理、创建和删改记录，以帮助自己在未来更好地回忆和理解对话历史。

本轮要维护的聊天ID：{chat_id}
本轮随机选中的起始记忆 ID：{start_memory_id if start_memory_id else '无（由你自行选择合适的切入点）'}

你可以使用的工具包括：
**ChatHistory 维护工具：**
- search_chat_history：根据关键词或参与人搜索该 chat_id 下的历史记忆概括列表
- get_chat_history_detail：查看某条概括的详细内容
- create_chat_history：创建一条新的 ChatHistory 概括记录
- update_chat_history：重写或精炼主题、概括、关键词、关键信息
- delete_chat_history：删除明显冗余、噪声、错误或无意义的记录

**Jargon（黑话）维护工具（只读）：**
- search_jargon：搜索 Jargon 记录（仅供参考，不可修改）

**通用工具：**
- finish_maintenance：完成维护工作时调用此工具结束本次运行

**工作目标**：
- 发现冗余、重复或高度相似的记录，并进行合并或删除
- 发现主题/概括过于含糊、啰嗦或缺少关键信息的记录，进行重写和精简
- summary要尽可能保持有用的信息
- 尽量保持信息的真实与可用性，不要凭空捏造事实

**合并准则**
- 你可以新建一个记录，然后删除旧记录来实现合并
- 如果两个或多个记录的主题相似，内容是对主题不同方面的信息或讨论，且信息量较少，则可以合并为一条记录
- 如果两个记录冲突，可以根据逻辑保留一个或者进行整合

**轮次信息**：
- 本次维护最多执行 {max_iterations} 轮
- 如果提前完成维护工作，可以调用 finish_maintenance 工具主动结束

**每一轮的执行方式（必须遵守）：**
- 第一步：先用一小段中文自然语言，写出你的「思考」和本轮计划
- 第二步：在这段思考之后，再通过工具调用来执行你的计划（可以调用 0~N 个工具）
- 第三步：收到工具结果后，在下一轮继续先写出新的思考，再视情况继续调用工具

请不要在没有先写出思考的情况下直接调用工具。
"""


async def run_dream_agent_once(
    chat_id: str,
    llm_client: LLMClient,
    max_iterations: int = 15,
    start_memory_id: Optional[int] = None,
    bot_name: str = "小易"
) -> Dict[str, Any]:
    """Run dream agent once for a specific chat_id.
    
    Args:
        chat_id: Chat ID to maintain
        llm_client: LLM client
        max_iterations: Maximum iterations
        start_memory_id: Starting memory ID (optional)
        bot_name: Bot name
        
    Returns:
        Dict with maintenance results
    """
    start_ts = time.time()
    logger.info(f"[Dream] 开始对 chat_id={chat_id} 进行维护，最多 {max_iterations} 轮")
    
    # Initialize tools
    tool_registry = _init_dream_tools(chat_id)
    tool_defs = tool_registry.get_tool_definitions()
    
    # Build prompt
    head_prompt = _build_dream_prompt(chat_id, bot_name, start_memory_id, max_iterations)
    
    # Conversation history
    conversation = [
        {"role": "system", "content": head_prompt}
    ]
    
    # Preload starting memory detail if provided
    if start_memory_id is not None:
        try:
            ai_db = get_ai_database()
            session = ai_db.get_session()
            try:
                record = session.query(ChatHistory).filter(ChatHistory.id == start_memory_id).first()
                if record:
                    start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.start_time)) if record.start_time else "未知"
                    end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.end_time)) if record.end_time else "未知"
                    
                    detail_text = f"""【起始记忆详情】
ID={record.id}
时间范围={start_time_str} 至 {end_time_str}
主题={record.theme or '无'}
关键词={record.keywords or '无'}
概括={record.summary or '无'}
关键信息={record.key_point or '无'}
"""
                    conversation.append({"role": "user", "content": detail_text})
            finally:
                session.close()
        except Exception as e:
            logger.error(f"[Dream] 预加载起始记忆失败: {e}")
    
    # Main loop
    iteration = 0
    finish_called = False
    
    for iteration in range(1, max_iterations + 1):
        # Add round info
        remaining = max_iterations - iteration + 1
        conversation.append({
            "role": "user",
            "content": f"【轮次信息】当前是第 {iteration}/{max_iterations} 轮，还剩 {remaining} 轮。"
        })
        
        # Call LLM with tools
        try:
            response = await llm_client.chat_completion_with_tools(
                messages=conversation,
                tools=tool_defs,
                temperature=0.4,
                max_tokens=2000
            )
            
            if not response:
                logger.error(f"[Dream] 第 {iteration} 轮 LLM 调用失败")
                break
            
            # Extract content and tool calls
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])
            
            if content:
                logger.debug(f"[Dream] 第 {iteration} 轮思考: {content[:200]}")
            
            # Add assistant message
            conversation.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls if tool_calls else None
            })
            
            # Execute tools
            if tool_calls:
                logger.info(f"[Dream] 第 {iteration} 轮调用 {len(tool_calls)} 个工具")
                
                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name")
                    tool_args = tool_call.get("function", {}).get("arguments", {})
                    call_id = tool_call.get("id", f"call_{iteration}")
                    
                    tool = tool_registry.get_tool(tool_name)
                    if not tool:
                        logger.warning(f"[Dream] 未知工具: {tool_name}")
                        continue
                    
                    # Check for finish_maintenance
                    if tool_name == "finish_maintenance":
                        finish_called = True
                    
                    # Execute tool
                    try:
                        result = await tool.execute(**tool_args)
                        logger.debug(f"[Dream] 工具 {tool_name} 执行完成")
                        
                        # Add tool response
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": tool_name,
                            "content": str(result)
                        })
                    except Exception as e:
                        logger.error(f"[Dream] 工具 {tool_name} 执行失败: {e}")
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": tool_name,
                            "content": f"工具执行失败: {str(e)}"
                        })
                
                if finish_called:
                    logger.info(f"[Dream] 第 {iteration} 轮检测到 finish_maintenance，提前结束")
                    break
            else:
                logger.debug(f"[Dream] 第 {iteration} 轮未调用任何工具")
        
        except Exception as e:
            logger.error(f"[Dream] 第 {iteration} 轮执行异常: {e}", exc_info=True)
            break
    
    cost = time.time() - start_ts
    logger.info(f"[Dream] 维护完成: chat_id={chat_id}, 共 {iteration} 轮, 耗时 {cost:.1f}s")
    
    return {
        "chat_id": chat_id,
        "iterations": iteration,
        "cost_seconds": cost,
        "finish_called": finish_called
    }


def _pick_random_chat_id() -> Optional[str]:
    """Pick a random chat_id that has >= 10 ChatHistory records."""
    try:
        ai_db = get_ai_database()
        session = ai_db.get_session()
        
        try:
            from sqlalchemy import func
            
            # Get chat_ids with >= 10 records
            rows = session.query(
                ChatHistory.chat_id,
                func.count(ChatHistory.id).label('cnt')
            ).group_by(ChatHistory.chat_id).having(
                func.count(ChatHistory.id) >= 10
            ).limit(200).all()
            
            eligible_ids = [row.chat_id for row in rows]
            
            if not eligible_ids:
                logger.warning("[Dream] 没有满足条件的 chat_id（记录数 >= 10）")
                return None
            
            chosen = random.choice(eligible_ids)
            logger.info(f"[Dream] 从 {len(eligible_ids)} 个 chat_id 中随机选择: {chosen}")
            return chosen
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"[Dream] 随机选择 chat_id 失败: {e}")
        return None


def _pick_random_memory_for_chat(chat_id: str) -> Optional[int]:
    """Pick a random ChatHistory record for the given chat_id."""
    try:
        ai_db = get_ai_database()
        session = ai_db.get_session()
        
        try:
            rows = session.query(ChatHistory.id).filter(
                ChatHistory.chat_id == chat_id
            ).order_by(ChatHistory.start_time.asc()).limit(200).all()
            
            ids = [row.id for row in rows]
            
            if not ids:
                logger.warning(f"[Dream] chat_id={chat_id} 没有 ChatHistory 记录")
                return None
            
            return random.choice(ids)
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"[Dream] 随机选择起始记忆失败: {e}")
        return None


async def run_dream_cycle_once(llm_client: LLMClient, bot_name: str = "小易") -> Optional[Dict[str, Any]]:
    """Run one dream cycle: pick a chat_id, pick a starting memory, and maintain.
    
    Args:
        llm_client: LLM client
        bot_name: Bot name
        
    Returns:
        Maintenance results or None
    """
    chat_id = _pick_random_chat_id()
    if not chat_id:
        return None
    
    start_memory_id = _pick_random_memory_for_chat(chat_id)
    
    result = await run_dream_agent_once(
        chat_id=chat_id,
        llm_client=llm_client,
        max_iterations=15,
        start_memory_id=start_memory_id,
        bot_name=bot_name
    )
    
    return result

