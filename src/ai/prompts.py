"""
AI系统统一提示词管理文件

此文件包含所有AI系统使用的提示词模板，方便统一管理和修改。
每个提示词都有详细注释说明其用途和使用位置。
"""

# ============================================================================
# 基础回复相关提示词
# ============================================================================

# 用途：默认系统提示词，当没有预设时使用
# 使用位置：src/ai/replyer.py - generate_reply()
DEFAULT_SYSTEM_PROMPT = "你是{bot_name}，一个友好、自然的AI助手。"

# 用途：工具使用规则说明，当AI需要使用工具时添加到系统提示词中
# 使用位置：src/ai/replyer.py - generate_reply()
TOOL_USAGE_RULES = """
[重要] 工具使用规则：
1. 正常对话回复时，直接返回文本内容即可，不要使用 send_group_message 或 send_private_message 工具。
2. 只有在需要@用户、回复特定消息、或跨群发送时，才使用消息发送工具。
3. 不要在回复文本中包含工具调用的XML格式（如 <arg_key>、<arg_value> 等），这些是系统内部格式。
4. 如果需要使用工具，使用标准的 tool_calls 格式，不要在文本中描述工具调用。
"""

# 用途：工具调用被拒绝时的系统消息
# 使用位置：src/ai/message_handler.py - _process_ai_message()
TOOL_REJECTION_MESSAGE = "工具调用已被拒绝，需要等待管理员审核。请停止调用工具，直接向用户说明情况。不要再尝试调用工具。"

# 用途：最后一轮工具调用时的强制回复提示
# 使用位置：src/ai/message_handler.py - _process_ai_message()
FINAL_ROUND_MESSAGE = "请根据以上工具调用结果，总结并回复用户。不要再调用工具，直接给出最终回复。"

# 用途：详细的工具使用规则和消息发送工具的特殊说明
# 使用位置：src/ai/message_handler.py - _process_ai_message()
def build_detailed_tool_usage_instructions(tool_names: list) -> str:
    """构建详细的工具使用规则提示词"""
    tool_list_str = ', '.join(tool_names[:10]) + ('...' if len(tool_names) > 10 else '')
    return f"""
重要工具使用规则：
1. 当用户要求执行操作（如搜索、TTS、群管理等）时，你必须使用工具调用（tool_calls）来执行，而不是在文本中描述你要做什么。
2. 你应该主动使用工具来提升交互体验，例如：
   - 当需要查询信息时，主动使用搜索工具
   - 当对话需要语音时，主动使用text_to_speech工具
   - 当需要执行群管理操作时，使用相应的群管理工具
3. 工具调用后，如果工具已经完成了操作，你不需要再发送确认消息。工具已经完成了任务，直接结束对话即可。
4. 只有在工具调用失败或需要补充说明时，才需要发送文本回复。
可用工具：{tool_list_str}

[重要] 关于消息发送工具的特殊说明：
1. send_group_message 和 send_private_message 是特殊用途工具，仅用于：
   - 需要@（艾特）用户时（使用send_group_message的at_user_ids参数）
   - 需要引用/回复某条消息时（使用reply_to_message_id参数）
   - 给其他群或用户发送消息时（跨群/跨用户发送）
   - 用户明确要求分段发送、多次发送、发送多条消息时（例如：'分段发送三条喜欢你'、'发送3条消息'等）
2. [重要] 正常对话回复不要使用这些工具！直接返回文本内容即可，系统会自动将你的文本回复发送到当前群或私聊。
3. 如果你只是要回复用户的问题或进行正常对话，直接返回文本，不要调用send_group_message或send_private_message工具。
4. [关键] 当用户要求分段发送或多次发送消息时，你必须多次调用send_group_message工具：
   - 例如：用户说'分段发送三条喜欢你'，你需要调用3次send_group_message工具，每次发送一条'喜欢你'的消息
   - 例如：用户说'发送20条消息'，你需要调用20次send_group_message工具
   - 每次工具调用只发送一条消息，不要在一次调用中发送多条消息
   - [重要] 你应该尽量在一次响应中返回所有需要的tool_calls，系统会依次执行所有工具调用
   - 例如：用户要求发送20条消息，你应该在一次响应中返回20个send_group_message的tool_calls，而不是分多轮调用
   - 只有在以下情况才需要分多轮调用：
     * 工具调用数量非常多（超过20个）时，可以分多轮调用
     * 需要用第一个工具的结果作为第二个工具的参数时（例如：先搜索获取信息，再用获取的信息发送消息）
   - 当你完成所有要求的消息发送后，返回纯文本响应（不包含工具调用），系统会自动退出循环
5. 使用send_group_message工具时，不要在message参数中包含@符号，系统会根据at_user_ids参数自动添加@。
6. 在正常文本回复中，不要包含@符号或@用户，因为系统会自动处理@功能。
7. 如果工具已经发送了消息，不要再次发送文本消息，避免重复。
"""

# ============================================================================
# 大脑规划器（Brain Planner）相关提示词
# ============================================================================

# 用途：构建大脑规划器的提示词，用于决定AI是否回复、等待或完成对话
# 使用位置：src/ai/brain_planner.py - _build_planner_prompt()
def build_planner_prompt(chat_context: str, bot_name: str, time_info: str = None, actions_history: str = None) -> str:
    """构建大脑规划器提示词"""
    time_block = ""
    if time_info:
        time_block = f"**当前时间**\n{time_info}\n\n"
    
    name_block = f"**你的身份**\n你的名字是{bot_name}\n\n"
    
    chat_desc = "你正在qq群里聊天"
    
    actions_block = ""
    if actions_history:
        actions_block = f"**之前的动作**\n{actions_history}\n\n"
    else:
        actions_block = "**之前的动作**\n暂无\n\n"
    
    return f"""{time_block}{name_block}{chat_desc}，以下是具体的聊天内容

**聊天内容**
{chat_context}

{actions_block}**可用的action**

reply
动作描述：
进行回复，你可以自然的顺着正在进行的聊天内容进行回复或自然的提出一个问题
{{
    "action": "reply",
    "target_message_id":"想要回复的消息id (格式: m数字)",
    "reason":"回复的原因"
}}

wait
动作描述：
暂时不再发言，等待指定时间。适用于以下情况：
- 你已经表达清楚一轮，想给对方留出空间
- 你感觉对方的话还没说完，或者自己刚刚发了好几条连续消息
- 你想要等待一定时间来让对方把话说完，或者等待对方反应
- 你想保持安静，专注"听"而不是马上回复
- 群里其他人正在对话，你没必要插嘴
- 消息内容不需要你回复（比如日常闲聊、他人之间的对话等）
请你根据上下文来判断要等待多久，请你灵活判断：
- 如果你们交流间隔时间很短，聊的很频繁，不宜等待太久
- 如果你们交流间隔时间很长，聊的很少，可以等待较长时间
{{
    "action": "wait",
    "target_message_id":"想要作为这次等待依据的消息id（通常是对方的最新消息）",
    "wait_seconds": 等待的秒数（必填，例如：5 表示等待5秒）,
    "reason":"选择等待的原因"
}}

complete_talk
动作描述：
当前聊天暂时结束了，对方离开，没有更多话题了
你可以使用该动作来暂时休息，等待对方有新发言再继续：
- 多次wait之后，对方迟迟不回复消息才用
- 如果对方只是短暂不回复，应该使用wait而不是complete_talk
- 聊天内容显示当前聊天已经结束或者没有新内容时候，选择complete_talk
选择此动作后，将不再继续循环思考，直到收到对方的新消息
{{
    "action": "complete_talk",
    "target_message_id":"触发完成对话的消息id（通常是对方的最新消息）",
    "reason":"选择完成对话的原因"
}}

请选择合适的action，并说明触发action的消息id和选择该action的原因。消息id格式:m+数字

**动作选择要求**
请你根据聊天内容,用户的最新消息和以下标准选择合适的动作:
- 仔细判断是否需要回复：不是每条消息都需要回复！
- 如果消息是针对你的、需要你回答的问题、或需要你参与的话题，才选择reply
- 如果是日常闲聊、其他人之间的对话、或不需要你参与的内容，选择wait或complete_talk
- 如果你刚回复过，应该给对方留出反应时间，选择wait
- 如果需要等待对方回复，使用wait动作
- 如果聊天已经结束，使用complete_talk动作
- 可以选择多个动作，但要合理

请选择所有符合使用要求的action，先输出你的选择思考理由（简短，不要分点），再输出你选择的action。
动作用json格式输出，每个json都要单独用```json包裹:

**示例**
// 理由文本
```json
{{
    "action":"reply",
    "target_message_id":"m5",
    "reason":"用户询问了一个问题，需要回答"
}}
```
```json
{{
    "action":"wait",
    "target_message_id":"m5",
    "wait_seconds": 3,
    "reason":"给对方留出时间思考"
}}
```

现在请输出你的思考和选择：
"""

# ============================================================================
# 梦境维护（Dream Agent）相关提示词
# ============================================================================

# 用途：构建梦境维护模式的提示词，用于AI自主维护聊天历史记录
# 使用位置：src/ai/dream/dream_agent.py - _build_dream_prompt()
def build_dream_prompt(chat_id: str, bot_name: str, start_memory_id: int = None, max_iterations: int = 10) -> str:
    """构建梦境维护提示词"""
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

# ============================================================================
# 聊天摘要（Chat Summarizer）相关提示词
# ============================================================================

# 用途：构建聊天记录摘要的提示词
# 使用位置：src/ai/chat_summarizer.py - _build_summary_prompt()
def build_chat_summary_prompt(chat_text: str) -> str:
    """构建聊天摘要提示词"""
    return f"""请总结以下聊天记录：

{chat_text}

要求：
1. 提取对话的主题（10字以内）
2. 写一段简洁的摘要（50-100字）
3. 提取3-5个关键词
4. 列出3-5个重要信息点
5. 列出参与者名单

请以 JSON 格式输出：
{{
  "theme": "对话主题",
  "summary": "对话摘要...",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "key_points": ["信息点1", "信息点2", "信息点3"],
  "participants": ["用户1", "用户2"]
}}
"""

# ============================================================================
# 黑话挖掘（Jargon Miner）相关提示词
# ============================================================================

# 用途：构建黑话提取的提示词
# 使用位置：src/ai/jargon_miner.py - _build_extraction_prompt()
def build_jargon_extraction_prompt(chat_str: str, bot_name: str) -> str:
    """构建黑话提取提示词"""
    return f"""{chat_str}

你的名字是{bot_name}，现在请你完成一个提取任务：

请从上面这段聊天内容中提取"可能是黑话"的候选项（黑话/俚语/网络缩写/口头禅）。

要求：
- 必须为对话中真实出现过的短词或短语
- 必须是你无法理解含义的词语，没有明确含义的词语
- 不要选择有明确含义，或者含义清晰的词语
- 排除：人名、@、表情包/图片中的内容、纯标点、常规功能词（如的、了、呢、啊等）
- 排除：SELF的发言中的词语
- 每个词条长度建议 2-8 个字符，尽量短小
- 最多提取30个黑话

黑话必须为以下几种类型：
- 由字母构成的，汉语拼音首字母的简写词，例如：nb、yyds、xswl
- 英文词语的缩写，用英文字母概括一个词汇或含义，例如：CPU、GPU、API
- 中文词语的缩写，用几个汉字概括一个词汇或含义，例如：社死、内卷

以 JSON 数组输出：
[
  {{"content": "词条1"}},
  {{"content": "词条2"}}
]

现在请输出 JSON 数组：
"""

# 用途：黑话含义推断（基于上下文）
# 使用位置：src/ai/jargon_miner.py - infer_jargon_meaning()
def build_jargon_inference_prompt_with_context(content: str, context_text: str) -> str:
    """构建黑话含义推断提示词（带上下文）"""
    return f"""**词条内容**
{content}

**词条出现的上下文**
{context_text}

请根据上下文，推断"{content}"这个词条的含义。
- 如果这是一个黑话、俚语或网络用语，请推断其含义
- 如果含义明确（常规词汇），也请说明
- 如果上下文信息不足，无法推断含义，请设置 no_info 为 true

以 JSON 格式输出：
{{
  "meaning": "详细含义说明",
  "no_info": false
}}
"""

# 用途：黑话含义推断（仅词条本身）
# 使用位置：src/ai/jargon_miner.py - infer_jargon_meaning()
def build_jargon_inference_prompt_content_only(content: str) -> str:
    """构建黑话含义推断提示词（仅词条）"""
    return f"""**词条内容**
{content}

请仅根据这个词条本身，推断其含义。
- 如果这是一个黑话、俚语或网络用语，请推断其含义
- 如果含义明确（常规词汇），也请说明

以 JSON 格式输出：
{{
  "meaning": "详细含义说明"
}}
"""

# 用途：黑话推断结果比较提示词
# 使用位置：src/ai/jargon_miner.py - infer_jargon_meaning()
def build_jargon_inference_comparison_prompt(inference1_meaning: str, inference2_meaning: str) -> str:
    """构建黑话推断结果比较提示词"""
    return f"""**推断结果1（基于上下文）**
{inference1_meaning}

**推断结果2（仅基于词条）**
{inference2_meaning}

请比较这两个推断结果，判断它们是否相同或类似。
- 如果两个推断结果的"含义"相同或类似，说明这个词条不是黑话（含义明确）
- 如果两个推断结果有差异，说明这个词条可能是黑话（需要上下文才能理解）

以 JSON 格式输出：
{{
  "is_similar": true/false,
  "reason": "判断理由"
}}
"""

# ============================================================================
# 表达学习（Expression Learner）相关提示词
# ============================================================================

# 用途：构建表达方式学习的提示词
# 使用位置：src/ai/expression_learner.py - _build_learning_prompt()
def build_expression_learning_prompt(chat_str: str, bot_name: str) -> str:
    """构建表达方式学习提示词"""
    return f"""{chat_str}

你的名字是{bot_name},现在请你完成一个提取任务:

请从上面这段群聊中提取用户的语言风格和说话方式

要求:
1. 只考虑文字,不要考虑表情包和图片
2. 不要总结SELF的发言,因为这是你自己的发言
3. 不要涉及具体的人名,也不要涉及具体名词
4. 思考有没有特殊的梗,一并总结成语言风格
5. 总结成如下格式的规律,总结的内容要详细,但具有概括性

格式要求:
- 每个表达方式格式为: "当[情境]时,[表达方式]"
- 情境描述不超过20个字,表达方式不超过20个字
- 提取3-10个表达方式
- 每个表达方式需要标注来源行编号 (上方聊天记录中方括号里的数字)

示例:
[
  {{"situation": "对某件事表示十分惊叹", "style": "使用 我嘞个xxxx", "source_id": "3"}},
  {{"situation": "表示讽刺的赞同,不讲道理", "style": "对对对", "source_id": "7"}},
  {{"situation": "涉及游戏相关时,夸赞,略带戏谑意味", "style": "使用 这么强!", "source_id": "12"}}
]

其中:
- situation: 表示"在什么情境下"的简短概括(不超过20个字)
- style: 表示对应的语言风格或常用表达(不超过20个字)
- source_id: 该表达方式对应的"来源行编号",即上方聊天记录中方括号里的数字,请只输出数字本身

现在请输出 JSON 数组：
"""

# 用途：表达方式选择提示词
# 使用位置：src/ai/expression_learner.py - select_expressions()
def build_expression_selection_prompt(context: str, expressions_str: str, reply_reason: str = None, max_count: int = 8) -> str:
    """构建表达方式选择提示词"""
    reason_text = f"\n回复理由: {reply_reason}" if reply_reason else ""
    return f"""根据以下聊天内容和回复理由,选择最合适的表达方式(最多{max_count}个):

聊天内容:
{context}
{reason_text}

可用的表达方式:
{expressions_str}

请选择最合适的表达方式编号(用逗号分隔,例如: 1,3,5):
"""

# ============================================================================
# 表达选择器（Expression Selector）相关提示词
# ============================================================================

# 用途：表达情境选择提示词
# 使用位置：src/ai/expression_selector.py - select_expressions()
def build_expression_situation_selection_prompt(
    chat_context: str, 
    situations_str: str, 
    reply_reason: str = None, 
    target_message: str = None, 
    max_count: int = 8
) -> str:
    """构建表达情境选择提示词"""
    context_block = ""
    if reply_reason:
        context_block = f"你的回复理由是：{reply_reason}\n"
    else:
        context_block = f"以下是正在进行的聊天内容：{chat_context}\n"
    
    target_block = ""
    target_extra = ""
    if target_message:
        target_block = f'，现在你想要对这条消息进行回复："{target_message}"'
        target_extra = "4. 考虑你要回复的目标消息\n"
    
    return f"""{context_block}{target_block}

以下是可选的表达情境：
{situations_str}

请你分析聊天内容的语境、情绪、话题类型，从上述情境中选择最适合当前聊天情境的，最多{max_count}个情境。

考虑因素包括：
1. 聊天的情绪氛围（轻松、严肃、幽默等）
2. 话题类型（日常、技术、游戏、情感等）
3. 情境与当前语境的匹配度
{target_extra}请以JSON格式输出，只需要输出选中的情境编号：
例如：
{{
    "selected_situations": [2, 3, 5, 7]
}}

请严格按照JSON格式输出：
"""

# 用途：情感分析提示词
# 使用位置：src/ai/expression_selector.py - analyze_emotion()
def build_emotion_analysis_prompt(text: str) -> str:
    """构建情感分析提示词"""
    return f"""分析以下文本的情感倾向，用一个词概括（如：开心、无语、赞同、难过、惊讶等）：

{text}

请只输出一个词：
"""

# ============================================================================
# 表达自动检查器（Expression Auto Checker）相关提示词
# ============================================================================

# 用途：表达方式质量评估提示词
# 使用位置：src/ai/expression_auto_checker.py - _build_evaluation_prompt()
def build_expression_evaluation_prompt(expressions_text: str) -> str:
    """构建表达方式质量评估提示词"""
    return f"""你是一个AI表达方式质量评估专家。请评估以下学习的表达方式的质量。

评估标准：
1. **接受条件**：
   - 表达方式自然、流畅
   - 情境描述清晰、具体
   - 没有明显的语法错误或病句
   - 不包含敏感、不当内容
   - 表达方式与情境匹配

2. **拒绝条件**：
   - 表达方式包含明显错误或无意义内容
   - 情境描述过于模糊或不准确
   - 包含占位符（如 [占位符]、<xxx>、{{xxx}}）
   - 包含 SELF、BOT、AI 等自我指代（除非情境明确需要）
   - 包含图片标记（如 [CQ:image...)、[图片]）
   - 包含链接或特殊代码
   - 表达方式与情境严重不匹配

待评估的表达方式：

{expressions_text}

请对每个表达方式进行评估，并以JSON格式输出结果：

{{
    "evaluations": [
        {{"id": 1, "accepted": true, "reason": "表达方式自然，情境清晰"}},
        {{"id": 2, "accepted": false, "reason": "包含占位符"}},
        ...
    ]
}}

只输出JSON，不要其他内容。"""

# ============================================================================
# 表情学习（Sticker Learner）相关提示词
# ============================================================================

# 用途：表情情境和情感分析提示词
# 使用位置：src/ai/sticker_learner.py - learn_sticker_usage()
def build_sticker_analysis_prompt(context: str, sticker_type: str) -> str:
    """构建表情分析提示词"""
    return f"""以下是聊天对话，其中使用了一个{sticker_type}类型的表情：

{context}

请分析在这个对话中，发送表情的人想要表达什么情境和情感。

输出格式（JSON）：
{{
    "situation": "简短描述使用该表情的情境，不超过20字",
    "emotion": "一个词描述情感，如：开心、无语、赞同、惊讶等"
}}

请只输出JSON，不要其他内容：
"""

# ============================================================================
# 表情选择器（Sticker Selector）相关提示词
# ============================================================================

# 用途：表情选择提示词
# 使用位置：src/ai/sticker_selector.py - select_stickers()
def build_sticker_selection_prompt(
    reply_content: str = None,
    chat_context: str = None,
    emotion: str = None,
    candidates_str: str = "",
    max_count: int = 3
) -> str:
    """构建表情选择提示词"""
    context_block = ""
    if reply_content:
        context_block = f"你即将发送的回复内容是：{reply_content}\n\n"
    elif chat_context:
        context_block = f"当前聊天上下文：{chat_context}\n\n"
    
    emotion_block = ""
    if emotion:
        emotion_block = f"你想要表达的情感是：{emotion}\n\n"
    
    return f"""{context_block}{emotion_block}以下是可用的表情/贴图选项：
{candidates_str}

请从上述选项中选择最适合当前情境的表情，最多选择 {max_count} 个。

选择标准：
1. 情感匹配度：表情的情感应该与回复内容或目标情感一致
2. 情境适配度：表情应该适合当前的对话情境
3. 自然度：使用表情应该感觉自然，不突兀

请以JSON格式输出选中的表情编号：
{{
    "selected_stickers": [1, 3, 5]
}}

请只输出JSON：
"""

# ============================================================================
# 用户画像（Person Profiler）相关提示词
# ============================================================================

# 用途：用户画像生成提示词
# 使用位置：src/ai/person_profiler.py - _build_profile_prompt()
def build_person_profile_prompt(user_text: str) -> str:
    """构建用户画像提示词"""
    return f"""请分析以下用户的聊天记录，生成用户画像：

{user_text}

要求：
1. 给这个用户起一个简短的称呼或标签（例如：技术大神、搞笑王、沉默寡言的小伙伴等）
2. 解释为什么给这个称呼
3. 提取3-5个关于这个用户的记忆点（性格特点、兴趣爱好、说话风格等）

请以 JSON 格式输出：
{{
  "person_name": "用户称呼",
  "name_reason": "起这个称呼的原因",
  "memory_points": [
    "记忆点1：喜欢讨论技术话题",
    "记忆点2：说话风格幽默风趣",
    "记忆点3：经常在晚上活跃"
  ]
}}
"""

# ============================================================================
# 群组画像（Group Profiler）相关提示词
# ============================================================================

# 用途：群组画像生成提示词
# 使用位置：src/ai/group_profiler.py - _build_profile_prompt()
def build_group_profile_prompt(chat_text: str, group_name: str = None) -> str:
    """构建群组画像提示词"""
    name_info = f"群名称：{group_name}\n" if group_name else ""
    return f"""{name_info}请分析以下群聊记录，生成群组画像：

{chat_text}

要求：
1. 描述这个群的整体氛围和印象（50-100字）
2. 总结这个群的主要话题和基本信息（30-50字）

请以 JSON 格式输出：
{{
  "impression": "群组氛围描述：这是一个...的群，成员之间...，大家经常讨论...",
  "topic": "主要话题：技术交流、日常闲聊等"
}}
"""

# ============================================================================
# 工具权限管理（Tool Permission Manager）相关提示词
# ============================================================================

# 用途：工具调用安全审核提示词
# 使用位置：src/ai/tool_permission_manager.py - _check_with_ai_approval()
def build_tool_permission_prompt(tool_name: str, tool_args: dict, user_qq: str, chat_type: str, chat_id: str) -> str:
    """构建工具权限审核提示词"""
    return f"""你是一个安全审核助手，需要判断以下工具调用是否合理和安全。

**工具信息**
- 工具名称: {tool_name}
- 工具参数: {tool_args}

**用户信息**
- 用户QQ: {user_qq}
- 聊天类型: {chat_type}
- 聊天ID: {chat_id}

**审核要求**
请判断这个工具调用是否:
1. 符合工具的正常使用场景
2. 参数是否合理（例如禁言时长不过分、不针对管理员等）
3. 没有明显的恶意或滥用倾向

**重要：请直接在回复中输出JSON，不要添加其他文字说明。**

请以 JSON 格式输出（必须严格按照以下格式，不要添加任何其他内容）：
{{
  "approved": true,
  "reason": "批准或拒绝的理由（简短说明，不超过50字）"
}}

或者

{{
  "approved": false,
  "reason": "拒绝的理由（简短说明，不超过50字）"
}}
"""

# ============================================================================
# 知识图谱（Knowledge Graph）相关提示词
# ============================================================================

# 用途：关键词提取提示词（用于知识图谱搜索）
# 使用位置：src/ai/knowledge/kg_manager.py - extract_keywords()
def build_keyword_extraction_prompt(query: str) -> str:
    """构建关键词提取提示词"""
    return f"""请从以下查询中提取关键词，用于搜索知识图谱。

查询：{query}

输出关键词列表（JSON格式）：
{{
    "keywords": ["关键词1", "关键词2", ...]
}}

只输出JSON。"""

# 用途：知识三元组提取提示词
# 使用位置：src/ai/knowledge/open_ie.py - _build_extraction_prompt()
def build_triple_extraction_prompt(text: str, max_triples: int = 10) -> str:
    """构建知识三元组提取提示词"""
    return f"""请从以下文本中提取知识三元组（Subject-Predicate-Object）。

文本：
{text}

要求：
1. 提取最多 {max_triples} 个最重要的知识三元组
2. 每个三元组包含：主语（subject）、谓语（predicate）、宾语（object）
3. 主语和宾语应该是具体的实体（人、地点、组织、物品、概念等）
4. 谓语应该是关系或动作
5. 为每个三元组评估置信度（0-1之间的小数）
6. 如果能识别实体类型，也请标注（person/place/organization/thing/concept/time/event）

输出格式（JSON）：
{{
    "triples": [
        {{
            "subject": "主语",
            "subject_type": "实体类型（可选）",
            "predicate": "谓语/关系",
            "object": "宾语",
            "object_type": "实体类型（可选）",
            "confidence": 0.9
        }}
    ]
}}

只输出JSON，不要其他内容。"""

# 用途：实体提取提示词
# 使用位置：src/ai/knowledge/open_ie.py - extract_entities()
def build_entity_extraction_prompt(text: str) -> str:
    """构建实体提取提示词"""
    return f"""请从以下文本中识别所有重要的实体（人、地点、组织、物品、概念等）。

文本：
{text}

输出格式（JSON）：
{{
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型（person/place/organization/thing/concept）",
            "description": "简短描述（可选）"
        }}
    ]
}}

只输出JSON。"""

# 用途：关系提取提示词
# 使用位置：src/ai/knowledge/open_ie.py - extract_relationships()
def build_relationship_extraction_prompt(entity1: str, entity2: str, text: str) -> str:
    """构建关系提取提示词"""
    return f"""在以下文本中，分析"{entity1}"和"{entity2}"之间的关系。

文本：
{text}

请列出它们之间的关系（如果有的话），以JSON格式输出：
{{
    "relationships": ["关系1", "关系2", ...]
}}

只输出JSON。"""

