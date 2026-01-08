"""AI system dedicated database models - inspired by RuaBot learning system.

This module contains all database models for RuaBot-style AI learning features:
- Expression learning (表达学习)
- Jargon learning (黑话学习)
- Chat history and memory (聊天历史和记忆)
- Knowledge graph (知识图谱)
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Expression(Base):
    """Expression/speaking style learned from users.
    
    Stores language patterns and speaking styles learned from chat messages.
    Used for making AI responses more natural and group-specific.
    """
    __tablename__ = 'ai_expressions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core fields
    situation = Column(Text, nullable=False)  # 情境描述 (e.g., "当对某件事表示惊叹时")
    style = Column(Text, nullable=False)  # 表达方式 (e.g., "使用 我嘞个xxxx")
    
    # Source tracking
    chat_id = Column(String(255), nullable=False, index=True)  # 来源聊天ID (group:群号 or user:QQ号)
    content_list = Column(JSON, nullable=True)  # 出现上下文列表 (JSON array of strings)
    
    # Statistics
    count = Column(Integer, nullable=False, default=1)  # 出现次数
    last_active_time = Column(Float, nullable=True)  # 最后活跃时间 (timestamp)
    create_date = Column(Float, nullable=True)  # 创建日期 (timestamp)
    
    # Quality control
    checked = Column(Boolean, nullable=False, default=False)  # 是否已检查
    rejected = Column(Boolean, nullable=False, default=False)  # 是否被拒绝
    modified_by = Column(String(50), nullable=True)  # 'ai' or 'user'
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Expression(situation='{self.situation[:20]}...', style='{self.style[:20]}...', count={self.count})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'situation': self.situation,
            'style': self.style,
            'chat_id': self.chat_id,
            'content_list': self.content_list,
            'count': self.count,
            'last_active_time': self.last_active_time,
            'create_date': self.create_date,
            'checked': self.checked,
            'rejected': self.rejected,
            'modified_by': self.modified_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Jargon(Base):
    """Jargon/slang terms learned from users.
    
    Tracks unknown words/phrases and gradually infers their meaning through context.
    Uses dual inference mechanism to identify true jargon vs. regular words.
    """
    __tablename__ = 'ai_jargons'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core fields
    content = Column(Text, nullable=False)  # 黑话内容
    meaning = Column(Text, nullable=True)  # 推断的含义
    
    # Source tracking
    chat_id = Column(String(255), nullable=False, index=True)  # 来源聊天ID
    raw_content = Column(JSON, nullable=True)  # 出现上下文列表 (JSON array)
    is_global = Column(Boolean, nullable=False, default=False)  # 是否全局黑话
    
    # Statistics
    count = Column(Integer, nullable=False, default=0)  # 出现次数
    
    # Inference control
    is_jargon = Column(Boolean, nullable=True)  # None=未判定, True=是黑话, False=不是黑话
    last_inference_count = Column(Integer, nullable=True)  # 最后一次推断时的count值
    is_complete = Column(Boolean, nullable=False, default=False)  # 是否已完成所有推断
    
    # Dual inference results (JSON格式)
    inference_with_context = Column(JSON, nullable=True)  # 基于上下文的推断结果
    inference_content_only = Column(JSON, nullable=True)  # 仅基于词条的推断结果
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Jargon(content='{self.content}', meaning='{self.meaning[:30] if self.meaning else 'None'}...', is_jargon={self.is_jargon})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'content': self.content,
            'meaning': self.meaning,
            'chat_id': self.chat_id,
            'raw_content': self.raw_content,
            'is_global': self.is_global,
            'count': self.count,
            'is_jargon': self.is_jargon,
            'last_inference_count': self.last_inference_count,
            'is_complete': self.is_complete,
            'inference_with_context': self.inference_with_context,
            'inference_content_only': self.inference_content_only,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatHistory(Base):
    """Summarized chat history for long-term memory.
    
    Stores summarized chat segments for memory retrieval and context building.
    """
    __tablename__ = 'ai_chat_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core fields
    chat_id = Column(String(255), nullable=False, index=True)  # 聊天ID
    start_time = Column(Float, nullable=False)  # 起始时间 (timestamp)
    end_time = Column(Float, nullable=False)  # 结束时间 (timestamp)
    
    # Content
    original_text = Column(Text, nullable=False)  # 对话原文
    summary = Column(Text, nullable=False)  # 概括
    theme = Column(Text, nullable=False)  # 主题
    
    # Metadata
    participants = Column(JSON, nullable=True)  # 参与者列表 (JSON array)
    keywords = Column(JSON, nullable=True)  # 关键词列表 (JSON array)
    key_point = Column(JSON, nullable=True)  # 关键信息点 (JSON array)
    
    # Statistics
    count = Column(Integer, nullable=False, default=0)  # 被检索次数
    forget_times = Column(Integer, nullable=False, default=0)  # 被遗忘检查次数
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ChatHistory(chat_id='{self.chat_id}', theme='{self.theme[:30]}...', count={self.count})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'original_text': self.original_text,
            'summary': self.summary,
            'theme': self.theme,
            'participants': self.participants,
            'keywords': self.keywords,
            'key_point': self.key_point,
            'count': self.count,
            'forget_times': self.forget_times,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MessageRecord(Base):
    """Raw message records for learning and analysis.
    
    Stores individual messages for expression learning, jargon mining, etc.
    """
    __tablename__ = 'ai_message_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core fields
    message_id = Column(String(255), nullable=True, index=True)  # OneBot消息ID
    chat_id = Column(String(255), nullable=False, index=True)  # 聊天ID
    
    # Message content
    plain_text = Column(Text, nullable=True)  # 纯文本消息
    display_message = Column(Text, nullable=True)  # 显示消息 (包含CQ码)
    
    # Sender info
    user_id = Column(String(255), nullable=False, index=True)  # 发送者QQ号
    user_nickname = Column(String(255), nullable=True)  # 用户昵称
    user_cardname = Column(String(255), nullable=True)  # 群名片
    
    # Chat info
    group_id = Column(String(255), nullable=True, index=True)  # 群号 (if group message)
    group_name = Column(String(255), nullable=True)  # 群名称
    
    # Metadata
    time = Column(Float, nullable=False, index=True)  # 消息时间戳
    is_bot_message = Column(Boolean, nullable=False, default=False)  # 是否是机器人自己的消息
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<MessageRecord(message_id='{self.message_id}', chat_id='{self.chat_id}', user_id='{self.user_id}')>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'plain_text': self.plain_text,
            'display_message': self.display_message,
            'user_id': self.user_id,
            'user_nickname': self.user_nickname,
            'user_cardname': self.user_cardname,
            'group_id': self.group_id,
            'group_name': self.group_name,
            'time': self.time,
            'is_bot_message': self.is_bot_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PersonInfo(Base):
    """Information about individual users/persons.
    
    Stores user profiles, impressions, and memory points about specific users.
    """
    __tablename__ = 'ai_person_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identity
    person_id = Column(String(255), unique=True, nullable=False, index=True)  # platform:user_id
    platform = Column(String(50), nullable=False)  # 'qq', 'discord', etc.
    user_id = Column(String(255), nullable=False, index=True)  # 用户ID
    
    # Names
    person_name = Column(String(255), nullable=True)  # 个人名称 (AI记住的名字)
    name_reason = Column(Text, nullable=True)  # 名称设定的原因
    nickname = Column(String(255), nullable=True)  # 用户昵称
    group_nick_name = Column(JSON, nullable=True)  # 群昵称列表 (JSON array of {group_id, nick})
    
    # Memory
    is_known = Column(Boolean, nullable=False, default=False)  # 是否已认识
    memory_points = Column(JSON, nullable=True)  # 记忆点 (JSON array)
    know_times = Column(Float, nullable=True)  # 认识时间 (timestamp)
    know_since = Column(Float, nullable=True)  # 首次印象总结时间
    last_know = Column(Float, nullable=True)  # 最后一次印象总结时间
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PersonInfo(person_id='{self.person_id}', person_name='{self.person_name}', is_known={self.is_known})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'person_id': self.person_id,
            'platform': self.platform,
            'user_id': self.user_id,
            'person_name': self.person_name,
            'name_reason': self.name_reason,
            'nickname': self.nickname,
            'group_nick_name': self.group_nick_name,
            'is_known': self.is_known,
            'memory_points': self.memory_points,
            'know_times': self.know_times,
            'know_since': self.know_since,
            'last_know': self.last_know,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class GroupInfo(Base):
    """Information about groups.
    
    Stores group profiles, topics, and member information.
    """
    __tablename__ = 'ai_group_info'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identity
    group_id = Column(String(255), unique=True, nullable=False, index=True)  # 群ID
    platform = Column(String(50), nullable=False)  # 'qq', 'discord', etc.
    group_name = Column(String(255), nullable=True)  # 群名称
    
    # Profile
    group_impression = Column(Text, nullable=True)  # 群组印象
    topic = Column(Text, nullable=True)  # 群组话题/基本信息
    member_list = Column(JSON, nullable=True)  # 成员列表 (JSON array)
    member_count = Column(Integer, nullable=True, default=0)  # 成员数量
    
    # Activity
    create_time = Column(Float, nullable=True)  # 创建时间 (timestamp)
    last_active = Column(Float, nullable=True)  # 最后活跃时间 (timestamp)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<GroupInfo(group_id='{self.group_id}', group_name='{self.group_name}', member_count={self.member_count})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'group_id': self.group_id,
            'platform': self.platform,
            'group_name': self.group_name,
            'group_impression': self.group_impression,
            'topic': self.topic,
            'member_list': self.member_list,
            'member_count': self.member_count,
            'create_time': self.create_time,
            'last_active': self.last_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Sticker(Base):
    """Sticker/emoji/image learned from users.
    
    Stores stickers, emojis, and images used in chat, along with their usage contexts
    and emotional meanings. Used for making AI responses more natural and expressive.
    """
    __tablename__ = 'ai_stickers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Core fields
    sticker_type = Column(String(50), nullable=False)  # 'image', 'face', 'emoji', 'sticker'
    sticker_id = Column(String(255), nullable=True)  # 表情包ID (如QQ表情ID、图片文件名等)
    sticker_url = Column(Text, nullable=True)  # 表情包URL (如果有)
    sticker_file = Column(String(255), nullable=True)  # 表情包文件名
    
    # Usage context
    situation = Column(Text, nullable=False)  # 使用情境 (e.g., "表示开心时")
    emotion = Column(String(50), nullable=True)  # 情感倾向 (e.g., "开心", "无语", "惊讶")
    meaning = Column(Text, nullable=True)  # 含义描述
    
    # Source tracking
    chat_id = Column(String(255), nullable=False, index=True)  # 来源聊天ID
    context_list = Column(JSON, nullable=True)  # 出现上下文列表 (JSON array of strings)
    
    # Statistics
    count = Column(Integer, nullable=False, default=1)  # 出现次数
    last_active_time = Column(Float, nullable=True)  # 最后活跃时间 (timestamp)
    create_date = Column(Float, nullable=True)  # 创建日期 (timestamp)
    
    # Quality control
    checked = Column(Boolean, nullable=False, default=False)  # 是否已检查
    rejected = Column(Boolean, nullable=False, default=False)  # 是否被拒绝
    modified_by = Column(String(50), nullable=True)  # 'ai' or 'user'
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Sticker(type='{self.sticker_type}', situation='{self.situation[:20]}...', count={self.count})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'sticker_type': self.sticker_type,
            'sticker_id': self.sticker_id,
            'sticker_url': self.sticker_url,
            'sticker_file': self.sticker_file,
            'situation': self.situation,
            'emotion': self.emotion,
            'meaning': self.meaning,
            'chat_id': self.chat_id,
            'context_list': self.context_list,
            'count': self.count,
            'last_active_time': self.last_active_time,
            'create_date': self.create_date,
            'checked': self.checked,
            'rejected': self.rejected,
            'modified_by': self.modified_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# Create indexes for better query performance
Index('idx_expression_chat_id_count', Expression.chat_id, Expression.count)
Index('idx_jargon_chat_id_count', Jargon.chat_id, Jargon.count)
Index('idx_chat_history_chat_id_time', ChatHistory.chat_id, ChatHistory.start_time)
Index('idx_message_record_chat_id_time', MessageRecord.chat_id, MessageRecord.time)
Index('idx_sticker_chat_id_count', Sticker.chat_id, Sticker.count)


# Export all models
AI_MODELS = [
    Expression,
    Jargon,
    ChatHistory,
    MessageRecord,
    PersonInfo,
    GroupInfo,
    Sticker,
]

