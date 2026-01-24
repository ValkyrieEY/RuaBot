# AI Features

{ [Chinese](ai-features_CN.md) | English }

## AI System Overview

RuaBot deeply integrates AI features, providing a complete intelligent dialogue system. The AI system supports various LLM models and features core functions such as expression learning, intelligent reply, knowledge management, and memory systems.

### Core Features

- **Multi-Model Support**: Supports various LLM models like OpenAI, MCP, etc.
- **Expression Learning**: Automatically learns user speaking styles and expression habits.
- **Intelligent Response**: Generates intelligent responses that fit the group chat style.
- **Slang Understanding**: Identifies and understands slang and jargon in group chats.
- **Knowledge Management**: Supports construction and management of knowledge graphs.
- **Memory System**: Maintains conversation history and context memory.
- **Continuous Learning**: Continuously optimizes expression methods and response quality.

## System Architecture

### AI Module Composition

```
AI Module
├── Model Management (ModelManager)
│   ├── Model Configuration
│   ├── Model Switching
│   └── Model Invocation
├── Message Processing (MessageHandler)
│   ├── Message Pre-processing
│   ├── Message Filtering
│   └── Message Conversion
├── Reply Generation (Replyer)
│   ├── Context Construction
│   ├── AI Invocation
│   └── Reply Optimization
├── Learning System
│   ├── Expression Learning (ExpressionLearner)
│   ├── Style Adaptation (ExpressionSelector)
│   └── Slang Understanding (JargonMiner)
├── Knowledge Management
│   ├── Knowledge Extraction (OpenIE)
│   ├── Knowledge Storage (KGStorage)
│   └── Knowledge Retrieval (KGManager)
└── Memory Management
    ├── Memory Storage
    ├── Memory Retrieval
    └── Memory Update
```

## Configuration Guide

### Global Configuration

Configure global AI settings via Web UI or API:

```json
{
  "enabled": true,
  "model_uuid": "model-uuid",
  "preset_uuid": "preset-uuid",
  "config": {
    "trigger_command": "@bot",
    "max_tokens": 2000,
    "temperature": 0.7
  }
}
```

### Group Configuration

Configure AI behavior for specific groups:

```json
{
  "config_type": "group",
  "target_id": "123456789",
  "enabled": true,
  "model_uuid": "model-uuid",
  "preset_uuid": "preset-uuid",
  "config": {
    "trigger_command": "",
    "reply_probability": 0.3
  }
}
```

### User Configuration

Configure AI behavior for specific users:

```json
{
  "config_type": "user",
  "target_id": "987654321",
  "enabled": true,
  "model_uuid": "model-uuid",
  "preset_uuid": "preset-uuid"
}
```

### Configuration Inheritance

- Group configuration inherits global configuration.
- User configuration inherits group and global configuration.
- Child configuration overrides parent configuration.

## Model Management

### Supported Models

#### OpenAI Models

- GPT-3.5-turbo
- GPT-4
- GPT-4-turbo
- Other OpenAI compatible models

#### MCP Models

Supports various models via MCP (Model Context Protocol).

### Adding Models

Add new models via Web UI or API:

```python
{
  "name": "Model Name",
  "type": "openai",
  "api_key": "your-api-key",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4"
}
```

### Model Switching

Models can be switched at runtime and take effect immediately.

## Preset Management

### Creating Presets

Presets define AI behavior style and prompts:

```json
{
  "name": "Preset Name",
  "system_prompt": "You are a friendly assistant...",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

### Preset Application

Different presets can be created for different scenarios:
- Daily chat preset
- Technical Q&A preset
- Entertainment interaction preset

## Expression Learning

### How it Works

The expression learning system analyzes messages in group chats to extract user expression styles:

1. **Message Collection**: Collect messages from group chats.
2. **Style Extraction**: Analyze message language style and word usage habits.
3. **Pattern Recognition**: Identify common expression patterns.
4. **Style Adaptation**: Apply learned styles when generating replies.

### Learning Configuration

```json
{
  "learning_enabled": true,
  "learning_rate": 0.1,
  "min_samples": 10,
  "update_interval": 3600
}
```

### Style Adaptation

The system automatically selects the most suitable expression style:
- Based on group style
- Based on conversation context
- Based on user preference

## Intelligent Reply

### Reply Generation Process

```
Message Reception
    │
    ▼
Message Pre-processing
    │
    ▼
Memory Retrieval
    │
    ├──► Group Memory
    ├──► User Memory
    └──► Session Memory
    │
    ▼
Context Construction
    │
    ├──► System Prompt
    ├──► Conversation History
    ├──► Related Knowledge
    └──► Style Prompt
    │
    ▼
AI Model Call
    │
    ▼
Reply Post-processing
    │
    ├──► Style Adaptation
    ├──► Content Optimization
    └──► Expression Selection
    │
    ▼
Reply Sending
```

### Trigger Methods

#### Command Trigger

Trigger AI reply using specific commands:

```
@bot hello
```

#### Probability Trigger

Automatically reply based on configured probability:

```json
{
  "reply_probability": 0.3
}
```

#### Keyword Trigger

Trigger when specific keywords are detected:

```json
{
  "trigger_keywords": ["question", "help", "how"]
}
```

### Reply Optimization

The system optimizes generated replies:

- **Style Adaptation**: Apply learned expression styles.
- **Length Control**: Control reply length.
- **Content Filtering**: Filter inappropriate content.
- **Emoji Addition**: Automatically add appropriate emojis.

## Slang Understanding

### Feature Description

The slang understanding system can identify and understand slang and jargon in group chats:

1. **Slang Mining**: Automatically mine slang from group chats.
2. **Slang Learning**: Learn the meaning and usage of slang.
3. **Slang Understanding**: Understand and use slang in conversations.

### Configuration

```json
{
  "jargon_mining_enabled": true,
  "jargon_threshold": 0.5,
  "update_interval": 7200
}
```

## Knowledge Management

### Knowledge Graph

The system supports building knowledge graphs to store and manage knowledge:

#### Knowledge Extraction

Automatically extract knowledge from conversations:

```python
{
  "entity": "Entity",
  "relation": "Relation",
  "target": "Target Entity"
}
```

#### Knowledge Storage

Knowledge is stored in a vector database for fast retrieval.

#### Knowledge Retrieval

Retrieve relevant knowledge when generating replies:

```python
{
  "query": "Query Content",
  "top_k": 5
}
```

### Knowledge Update

The knowledge graph is continuously updated:
- Automatically extract new knowledge from conversations.
- Periodically update knowledge relations.
- Clean up obsolete knowledge.

## Memory Management

### Memory Types

#### Group Memory

Store group-level conversation history:

```python
{
  "memory_type": "group",
  "target_id": "123456789",
  "messages": [...],
  "message_count": 100
}
```

#### User Memory

Store user-level conversation history:

```python
{
  "memory_type": "user",
  "target_id": "987654321",
  "messages": [...],
  "message_count": 50
}
```

#### Session Memory

Store context of the current session:

```python
{
  "memory_type": "session",
  "target_id": "session-id",
  "messages": [...]
}
```

### Memory Retrieval

Retrieve relevant memory when generating replies:

```python
{
  "memory_type": "group",
  "target_id": "123456789",
  "query": "Query Content",
  "limit": 10
}
```

### Memory Update

Memory automatically updates with conversations:
- Add new messages to memory.
- Periodically clean up old memory.
- Compress long memory.

## Advanced Features

### Dream System

The Dream System is an advanced AI feature supporting:

- **Autonomous Thinking**: AI can think and analyze autonomously.
- **Task Planning**: Plan complex tasks.
- **Tool Usage**: Use various tools to complete tasks.

#### Configuration

```json
{
  "dream_enabled": true,
  "dream_interval": 3600,
  "max_dream_steps": 10
}
```

### Frequency Control

Control AI reply frequency to avoid spamming:

```json
{
  "frequency_control": {
    "max_replies_per_minute": 5,
    "cooldown_period": 60
  }
}
```

### Group Profile

The system generates profiles for each group:

```json
{
  "group_id": "123456789",
  "profile": {
    "topic": "Tech Discussion",
    "style": "Formal",
    "activity": "High"
  }
}
```

### User Profile

The system generates profiles for each user:

```json
{
  "user_id": "987654321",
  "profile": {
    "interests": ["Coding", "Gaming"],
    "style": "Relaxed",
    "activity": "Medium"
  }
}
```

## Best Practices

### 1. Model Selection

- Use GPT-3.5-turbo for daily chat.
- Use GPT-4 for complex tasks.
- Choose appropriate models based on needs.

### 2. Preset Configuration

- Create different presets for different scenarios.
- Periodically optimize preset prompts.
- Test preset effects.

### 3. Memory Management

- Periodically clean up old memory.
- Control memory size.
- Optimize memory retrieval.

### 4. Frequency Control

- Set reasonable reply frequency.
- Avoid excessive replies.
- Adjust based on group activity.

### 5. Learning Optimization

- Periodically check learning effects.
- Adjust learning parameters.
- Clean up invalid learning data.

## Performance Optimization

### Caching Mechanism

- Model response caching.
- Memory retrieval caching.
- Knowledge retrieval caching.

### Asynchronous Processing

All AI operations are asynchronous and do not block the main thread.

### Batch Processing

Supports batch processing of multiple requests to improve efficiency.

## Monitoring and Debugging

### Log Viewing

View AI-related logs:

```bash
tail -f logs/onebot_framework.log | grep AI
```

### Performance Monitoring

Monitor AI performance via Web UI:
- Response time
- Call count
- Error rate

### Debug Mode

Enable debug mode to view detailed information:

```json
{
  "debug": true,
  "log_level": "DEBUG"
}
```

## FAQ

### 1. AI Not Replying

**Issue**: AI configured but not replying.

**Solution**:
- Check if AI is enabled.
- Check if trigger conditions are correct.
- Check logs for errors.
- Check if model configuration is correct.

### 2. Poor Reply Quality

**Issue**: AI reply quality is not ideal.

**Solution**:
- Optimize system prompts.
- Adjust temperature parameter.
- Increase context memory.
- Use a better model.

### 3. Excessive Memory Usage

**Issue**: Memory data takes up too much space.

**Solution**:
- Periodically clean up old memory.
- Limit memory length.
- Compress memory data.

### 4. Learning Effect Not Obvious

**Issue**: Expression learning effect is not obvious.

**Solution**:
- Increase learning samples.
- Adjust learning parameters.
- Check learning data quality.

## Reference Resources

- [Model Manager API](../src/ai/model_manager.py)
- [Reply Generator](../src/ai/replyer.py)
- [Expression Learner](../src/ai/expression_learner.py)
- [Knowledge Manager](../src/ai/knowledge/)

---

For more details, please refer to relevant API documentation and source code.

