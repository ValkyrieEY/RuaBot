# System Architecture and Logic Principle

{ [Chinese](architecture_CN.md) | English }

## Overall Architecture

RuaBot adopts a layered architecture design, with clear responsibilities for each layer, facilitating maintenance and expansion.

### Architecture Layers

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  ┌──────────────┐  ┌──────────────┐     │
│  │   Web UI     │  │   REST API   │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Application Layer               │
│  ┌──────────────┐  ┌──────────────┐     │
│  │   Router     │  │   Security   │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Business Layer                  │
│  ┌──────────────┐  ┌──────────────┐     │
│  │   Plugins    │  │      AI      │     │
│  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐     │
│  │   Protocol   │  │   EventBus   │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Core Layer                      │
│  ┌──────────────┐  ┌──────────────┐     │
│  │    Config    │  │   Database   │     │
│  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐     │
│  │    Logger    │  │   Storage    │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Protocol Layer                  │
│         OneBot v11 Protocol             │
└─────────────────────────────────────────┘
```

## Core Module Description

### 1. Core Module

The Core module provides basic services and is the cornerstone of the entire framework.

#### Configuration Management (Config)

- **Function**: Unified configuration management system.
- **Features**: 
  - Supports TOML configuration files.
  - Supports environment variable overrides.
  - Supports hot reload.
  - Type-safe configuration access.
- **Implementation**: `src/core/config.py`

#### Database (Database)

- **Function**: Data persistence service.
- **Features**:
  - Asynchronous database operations.
  - SQLAlchemy ORM.
  - Supports SQLite.
  - Database migrations.
- **Implementation**: `src/core/database.py`

#### Logging System (Logger)

- **Function**: Graded logging.
- **Features**:
  - Multi-level logging (DEBUG, INFO, WARNING, ERROR).
  - File logging and console logging.
  - Log rotation.
  - Structured logging.
- **Implementation**: `src/core/logger.py`

#### Event Bus (EventBus)

- **Function**: Event publishing and subscription mechanism.
- **Features**:
  - Asynchronous event processing.
  - Event filtering.
  - Event priority.
  - Event interception.
- **Implementation**: `src/core/event_bus.py`

#### Storage (Storage)

- **Function**: General storage service.
- **Features**:
  - Key-value storage.
  - Plugin data isolation.
  - Data persistence.
- **Implementation**: `src/core/storage.py`

### 2. Plugin Module

The plugin system is the core of the framework's extensibility.

#### Plugin Manager (PluginManager)

- **Function**: Plugin lifecycle management.
- **Features**:
  - Plugin loading and unloading.
  - Plugin hot reload.
  - Plugin dependency management.
  - Plugin configuration management.
- **Implementation**: `src/plugins/manager.py`

#### Plugin Interface (PluginInterface)

- **Function**: Standardized plugin interface.
- **Features**:
  - Lifecycle hooks.
  - Event handling interface.
  - Capability registration interface.
- **Implementation**: `src/plugins/interface.py`

#### Plugin Runtime

- **Function**: Plugin runtime management.
- **Features**:
  - Independent process execution.
  - Plugin loading and lifecycle management.
  - Runtime environment provision.
- **Implementation**: `src/plugins/runtime/`

#### Capability Registration (CapabilityRegistry)

- **Function**: Plugin capability registration and discovery.
- **Features**:
  - Capability registration.
  - Capability query.
  - Capability dependencies.
- **Implementation**: `src/plugins/capability_registry.py`

#### Interceptor (Interceptor)

- **Function**: Event interception and handling.
- **Features**:
  - Event interception.
  - Event modification.
  - Event filtering.
- **Implementation**: `src/plugins/interceptor.py`

### 3. AI Module

The AI module provides intelligent interaction capabilities.

#### AI Manager (AIManager)

- **Function**: Unified management of AI functions.
- **Features**:
  - AI configuration management.
  - Memory management.
  - Model switching.
- **Implementation**: `src/ai/ai_manager.py`

#### Model Management (ModelManager)

- **Function**: LLM model management.
- **Features**:
  - Multi-model support.
  - Model switching.
  - Model configuration.
- **Implementation**: `src/ai/model_manager.py`

#### Message Processing (MessageHandler)

- **Function**: Message pre-processing and post-processing.
- **Features**:
  - Message parsing.
  - Message filtering.
  - Message conversion.
- **Implementation**: `src/ai/message_handler.py`

#### Reply Generation (Replyer)

- **Function**: Intelligent reply generation.
- **Features**:
  - Context understanding.
  - Style adaptation.
  - Reply optimization.
- **Implementation**: `src/ai/replyer.py`

#### Expression Learning (ExpressionLearner)

- **Function**: Learning user expression styles.
- **Features**:
  - Style extraction.
  - Pattern recognition.
  - Style adaptation.
- **Implementation**: `src/ai/expression_learner.py`

#### Knowledge Management (KnowledgeManager)

- **Function**: Knowledge graph management.
- **Features**:
  - Knowledge extraction.
  - Knowledge storage.
  - Knowledge retrieval.
- **Implementation**: `src/ai/knowledge/`

#### Memory Management (MemoryRetrieval)

- **Function**: Conversation memory management.
- **Features**:
  - Memory storage.
  - Memory retrieval.
  - Memory updates.
- **Implementation**: `src/ai/memory_retrieval.py`

### 4. Protocol Module

The protocol module handles the OneBot protocol.

#### OneBot Protocol (OneBot)

- **Function**: OneBot v11 protocol implementation.
- **Features**:
  - Message reception.
  - Message sending.
  - Event handling.
  - API calls.
- **Implementation**: `src/protocol/onebot.py`

#### Message Processing (Message)

- **Function**: Message parsing and construction.
- **Features**:
  - Message type identification.
  - Message content parsing.
  - Message construction.
- **Implementation**: `src/protocol/message.py`

#### Event Processing (Events)

- **Function**: Event reception and distribution.
- **Features**:
  - Event type identification.
  - Event data parsing.
  - Event distribution.
- **Implementation**: `src/protocol/events.py`

### 5. Security Module

The security module provides security functions.

#### Authentication & Authorization (Auth)

- **Function**: User authentication and authorization.
- **Features**:
  - Login authentication.
  - Token management.
  - Session management.
- **Implementation**: `src/security/auth.py`

#### Permission Management (Permissions)

- **Function**: Granular permission control.
- **Features**:
  - Permission definition.
  - Permission checking.
  - Permission inheritance.
- **Implementation**: `src/security/permissions.py`

#### Access Control (AccessControl)

- **Function**: Access control list management.
- **Features**:
  - ACL definition.
  - ACL checking.
  - ACL updates.
- **Implementation**: `src/security/access_control.py`

#### Audit Logging (Audit)

- **Function**: Security audit logging.
- **Features**:
  - Operation recording.
  - Log querying.
  - Log analysis.
- **Implementation**: `src/security/audit.py`

## Workflow

### Message Processing Flow

```
User Message
    │
    ▼
OneBot Protocol Reception
    │
    ▼
Event Bus Publishes Message Event
    │
    ├──► Interceptor Processing
    │
    ├──► Plugin Subscription Processing
    │
    └──► AI Module Processing
         │
         ├──► Message Recording
         ├──► Memory Retrieval
         ├──► Context Construction
         ├──► AI Model Call
         ├──► Reply Generation
         └──► Reply Sending
```

### Plugin Loading Flow

```
Plugin Discovery
    │
    ▼
Read plugin.json
    │
    ▼
Check Dependencies
    │
    ▼
Select Adapter
    │
    ▼
Load Plugin Code
    │
    ▼
Create Plugin Instance
    │
    ▼
Call on_load
    │
    ▼
Register Capabilities
    │
    ▼
Call on_enable
    │
    ▼
Plugin Ready
```

### AI Reply Flow

```
Message Reception
    │
    ▼
Message Pre-processing
    │
    ▼
Memory Retrieval
    │
    ▼
Context Construction
    │
    ├──► Group Memory
    ├──► User Memory
    └──► Session Memory
    │
    ▼
AI Model Call
    │
    ├──► Model Selection
    ├──► Prompt Construction
    └──► Generate Reply
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
    │
    ▼
Memory Update
```

## Core Mechanisms

### Event-Driven Mechanism

RuaBot uses an event-driven architecture where all functions communicate via events:

1. **Event Publishing**: System or plugins publish events to the event bus.
2. **Event Subscription**: Plugins or modules subscribe to interested events.
3. **Event Processing**: Subscribers process events asynchronously.
4. **Event Interception**: Interceptors can intercept and modify events.

### Plugin Lifecycle

Plugins have a complete lifecycle:

1. **Discovery**: System discovers plugin directory.
2. **Loading**: Load plugin code and configuration.
3. **Initialization**: Call `on_load` hook.
4. **Enable**: Call `on_enable` hook.
5. **Run**: Plugin runs normally.
6. **Disable**: Call `on_disable` hook.
7. **Unload**: Call `on_unload` hook.

### Configuration Management Mechanism

Configuration management supports multi-level configuration:

1. **Default Configuration**: Default values in code.
2. **Configuration File**: TOML configuration file.
3. **Environment Variables**: Environment variable overrides.
4. **Runtime Configuration**: Dynamic configuration at runtime.

### Permission Check Mechanism

Permission checking uses chain checking:

1. **Global Permissions**: Check global permission settings.
2. **Group Permissions**: Check group permission settings.
3. **User Permissions**: Check user permission settings.
4. **Tool Permissions**: Check tool permission settings.

### Memory Management Mechanism

Memory management uses layered storage:

1. **Session Memory**: Context of current session.
2. **User Memory**: User-level history.
3. **Group Memory**: Group-level history.
4. **Global Memory**: Globally shared knowledge.

## Data Flow

### Message Data Flow

```
OneBot Message
    │
    ▼
Message Parsing
    │
    ▼
Event Construction
    │
    ▼
Event Bus
    │
    ├──► Plugin Processing
    └──► AI Processing
         │
         ├──► Message Recording
         ├──► Memory Retrieval
         ├──► AI Generation
         └──► Reply Construction
              │
              ▼
         OneBot Reply
```

### Configuration Data Flow

```
Configuration File (TOML)
    │
    ▼
Configuration Parsing
    │
    ▼
Environment Variable Override
    │
    ▼
Configuration Object
    │
    ├──► Cache
    └──► Application
```

### Plugin Data Flow

```
Plugin Directory
    │
    ├──► plugin.json (Metadata)
    ├──► system.json (System Data)
    └──► data/config.json (Config Data)
    │
    ▼
Plugin Loading
    │
    ▼
Plugin Instance
    │
    ├──► Register Capabilities
    ├──► Subscribe to Events
    └──► Provide Services
```

## Performance Optimization

### Asynchronous Processing

- All I/O operations are asynchronous.
- Event processing uses asynchronous mechanisms.
- Database operations use asynchronous ORM.

### Caching Mechanism

- Configuration caching.
- Plugin metadata caching.
- AI configuration caching.
- Memory caching.

### Connection Pooling

- Database connection pool.
- HTTP connection pool.
- WebSocket connection management.

### Resource Management

- Thread pool management.
- Memory management.
- File handle management.

## Extensibility Design

### Plugin Extension

- Standardized plugin interface.
- Flexible adapter system.
- Comprehensive lifecycle management.

### Protocol Extension

- Supports protocol extension.
- Supports custom message types.
- Supports custom event types.

### AI Extension

- Supports multiple LLM models.
- Supports custom AI features.
- Supports custom learning algorithms.

## Security Design

### Authentication & Authorization

- Token authentication.
- Session management.
- Permission verification.

### Data Security

- Configuration encryption.
- Sensitive data protection.
- Audit logging.

### Access Control

- IP whitelist.
- Rate limiting.
- Request verification.

