"""AI system database models."""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, JSON, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AIConfig(Base):
    """AI configuration model.
    
    Stores AI settings for global, group, or user level.
    """
    __tablename__ = 'ai_configs'
    
    # Composite primary key
    config_type = Column(String(50), primary_key=True, nullable=False)  # 'global', 'group', 'user'
    target_id = Column(String(255), primary_key=True, nullable=True)  # 群号或用户QQ，global类型为None
    
    # Function switches
    enabled = Column(Boolean, nullable=False, default=False)  # 总开关
    model_uuid = Column(String(255), nullable=True)  # 使用的模型UUID
    preset_uuid = Column(String(255), nullable=True)  # 使用的预设UUID
    
    # Statistics
    message_count = Column(Integer, nullable=False, default=0)  # 对话量
    
    # Additional config
    config = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIConfig(type='{self.config_type}', target='{self.target_id}', enabled={self.enabled})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'config_type': self.config_type,
            'target_id': self.target_id,
            'enabled': self.enabled,
            'model_uuid': self.model_uuid,
            'preset_uuid': self.preset_uuid,
            'message_count': self.message_count,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LLMModel(Base):
    """LLM model configuration."""
    
    __tablename__ = 'llm_models'
    
    uuid = Column(String(255), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(String(100), nullable=False)  # openai, anthropic, deepseek, etc.
    model_name = Column(String(255), nullable=False)  # gpt-4, claude-3, etc.
    api_key = Column(Text, nullable=True)  # 加密存储
    base_url = Column(String(500), nullable=True)  # 自定义API地址
    is_default = Column(Boolean, nullable=False, default=False)
    
    # Model capabilities
    supports_tools = Column(Boolean, nullable=False, default=False)  # 是否支持工具调用
    supports_vision = Column(Boolean, nullable=False, default=False)  # 是否支持视觉
    
    # Additional config
    config = Column(JSON, nullable=False, default=dict)  # temperature, max_tokens等
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<LLMModel(uuid='{self.uuid}', name='{self.name}', provider='{self.provider}')>"
    
    def to_dict(self, include_secret=False):
        """Convert to dictionary.
        
        Args:
            include_secret: Whether to include API key (default: False)
        """
        result = {
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'provider': self.provider,
            'model_name': self.model_name,
            'base_url': self.base_url,
            'is_default': self.is_default,
            'supports_tools': self.supports_tools,
            'supports_vision': self.supports_vision,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_secret:
            result['api_key'] = self.api_key
        
        return result


class AIPreset(Base):
    """AI preset (system prompt) configuration."""
    
    __tablename__ = 'ai_presets'
    
    uuid = Column(String(255), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)  # 系统提示词
    
    # Model parameters
    temperature = Column(Float, nullable=False, default=1.0)
    max_tokens = Column(Integer, nullable=False, default=2000)
    top_p = Column(Float, nullable=True)
    top_k = Column(Integer, nullable=True)
    
    # Additional config
    config = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIPreset(uuid='{self.uuid}', name='{self.name}')>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'top_p': self.top_p,
            'top_k': self.top_k,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AIMemory(Base):
    """AI conversation memory.
    
    Stores conversation history for groups or users.
    Groups share memory, private chats are independent.
    """
    __tablename__ = 'ai_memories'
    
    uuid = Column(String(255), primary_key=True, nullable=False)
    memory_type = Column(String(50), nullable=False, index=True)  # 'group' or 'user'
    target_id = Column(String(255), nullable=False, index=True)  # 群号或用户QQ
    preset_uuid = Column(String(255), nullable=True, index=True)  # 关联的预设UUID
    
    # Memory content (message history)
    messages = Column(JSON, nullable=False, default=list)  # [{"role": "user", "content": "..."}, ...]
    
    # Metadata
    message_count = Column(Integer, nullable=False, default=0)
    last_active = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIMemory(type='{self.memory_type}', target='{self.target_id}', count={self.message_count})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'uuid': self.uuid,
            'memory_type': self.memory_type,
            'target_id': self.target_id,
            'preset_uuid': self.preset_uuid,
            'messages': self.messages,
            'message_count': self.message_count,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MCPServer(Base):
    """MCP (Model Context Protocol) server configuration."""
    
    __tablename__ = 'mcp_servers'
    
    uuid = Column(String(255), primary_key=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    mode = Column(String(50), nullable=False)  # 'stdio' or 'sse'
    
    # stdio mode config
    command = Column(String(500), nullable=True)  # 命令
    args = Column(JSON, nullable=False, default=list)  # 参数列表
    env = Column(JSON, nullable=False, default=dict)  # 环境变量
    
    # SSE mode config
    url = Column(String(500), nullable=True)  # SSE URL
    headers = Column(JSON, nullable=False, default=dict)  # HTTP headers
    timeout = Column(Integer, nullable=True, default=10)  # 超时时间
    
    # Additional config
    config = Column(JSON, nullable=False, default=dict)
    
    # Connection status (runtime only, not stored in DB)
    status = Column(String(50), nullable=True)  # 'connecting', 'connected', 'error'
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<MCPServer(uuid='{self.uuid}', name='{self.name}', mode='{self.mode}', enabled={self.enabled})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'mode': self.mode,
            'command': self.command,
            'args': self.args,
            'env': self.env,
            'url': self.url,
            'headers': self.headers,
            'timeout': self.timeout,
            'config': self.config,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

