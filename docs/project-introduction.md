# Project Introduction

{ [Chinese](project-introduction_CN.md) | English }

## Project Overview

RuaBot is a modern QQ bot framework based on the OneBot v11 protocol, designed to provide developers with a powerful, easily extensible, and high-performance bot development platform.

### Design Philosophy

RuaBot's design follows these core principles:

- **Modularity**: Adopts a modular design where each functional module is independent, facilitating maintenance and expansion.
- **Extensibility**: Provides a comprehensive plugin system supporting third-party plugin development.
- **High Performance**: Based on multi-threading/asynchronous architecture, supporting high concurrency processing.
- **Ease of Use**: Provides friendly APIs and a Web management interface.
- **Intelligence**: Deep integration of AI features, supporting natural language processing and intelligent responses.

### Positioning

RuaBot is suitable for the following scenarios:

- QQ group chat bot development
- Intelligent customer service systems
- Automated task processing
- Content management and distribution
- Data collection and analysis

## Core Features

### 1. Plugin System

RuaBot provides a complete plugin system supporting:

- **Hot Loading**: Plugins can be dynamically loaded and unloaded at runtime.
- **Hot Reloading**: Supports automatic reloading after plugin code updates.
- **Dependency Management**: Supports management of dependencies between plugins.
- **Lifecycle Management**: Provides complete plugin lifecycle hooks.
- **Configuration Management**: Each plugin has an independent configuration system.
- **Adapter System**: Supports multiple plugin adapters.

### 2. AI Integration

RuaBot deeply integrates AI capabilities:

- **Multi-Model Support**: Supports various LLM models like OpenAI, MCP, etc.
- **Expression Learning**: Automatically learns user speaking styles and expression habits.
- **Intelligent Response**: Generates intelligent responses that fit the group chat style.
- **Slang Understanding**: Identifies and understands slang and jargon in group chats.
- **Knowledge Management**: Supports construction and management of knowledge graphs.
- **Memory System**: Maintains conversation history and context memory.
- **Continuous Learning**: Continuously optimizes expression methods and response quality.

### 3. Event-Driven Architecture

Adopts an event-driven architecture, providing:

- **Event Bus**: Unified event publishing and subscription mechanism.
- **Asynchronous Processing**: All event processing is asynchronous.
- **Event Interception**: Supports event interception and modification.
- **Event Filtering**: Supports event filtering and processing priorities.

### 4. Permission Management

A comprehensive permission management system:

- **Granular Control**: Supports multi-dimensional permission control for users, groups, tools, etc.
- **Permission Inheritance**: Supports permission inheritance and overriding.
- **Dynamic Permissions**: Supports runtime permission checking and modification.
- **Audit Logging**: Records all permission-related operations.

### 5. Web Management Interface

A modern Web management interface:

- **Real-time Configuration**: Supports real-time configuration modification and application.
- **Plugin Management**: Visualized plugin management interface.
- **AI Configuration**: Convenient AI model and configuration management.
- **System Monitoring**: Real-time system status monitoring.
- **Log Viewing**: Online log viewing and analysis.

## Architecture Design

### Overall Architecture

RuaBot uses a layered architecture design:

```
┌─────────────────────────────────────┐
│         Web UI (React)              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      API Layer (FastAPI)            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Core Layer                     │
│  ┌──────────┐  ┌──────────┐        │
│  │  Config  │  │ Database │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │  Logger  │  │ EventBus │        │
│  └──────────┘  └──────────┘        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Business Layer                    │
│  ┌──────────┐  ┌──────────┐        │
│  │ Plugins  │  │    AI    │        │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐  ┌──────────┐        │
│  │ Protocol │  │ Security │        │
│  └──────────┘  └──────────┘        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Protocol Layer (OneBot v11)       │
└─────────────────────────────────────┘
```

### Core Modules

#### 1. Core Module

The Core module provides basic functions:

- **Configuration Management**: Unified configuration management system supporting hot reload.
- **Database**: Asynchronous database operations and model management.
- **Log System**: Graded log recording and management.
- **Event Bus**: Event publishing and subscription mechanism.

#### 2. Plugin Module

Plugin system module:

- **Plugin Manager**: Loading, unloading, and reloading of plugins.
- **Plugin Interface**: Standardized plugin interface definition.
- **Adapter System**: Supports multiple plugin adapters.
- **Capability Registration**: Plugin capability registration and discovery.

#### 3. AI Module

AI function module:

- **Model Management**: Management and switching of LLM models.
- **Message Processing**: Pre-processing and post-processing of messages.
- **Response Generation**: Generation and optimization of intelligent responses.
- **Learning System**: Expression learning and style adaptation.
- **Knowledge Management**: Construction and management of knowledge graphs.
- **Memory Management**: Maintenance of conversation history and context.

#### 4. Protocol Module

Protocol processing module:

- **OneBot Protocol**: Implementation of OneBot v11 protocol.
- **Message Processing**: Parsing and construction of messages.
- **Event Processing**: Reception and distribution of events.
- **Response Processing**: Construction and sending of responses.

#### 5. Security Module

Security module:

- **Authentication & Authorization**: User authentication and authorization.
- **Permission Management**: Granular permission control.
- **Access Control**: Access control list management.
- **Audit Logging**: Security audit logs.

## Core Concepts

### Plugin

Plugins are the basic unit of extension for RuaBot. Each plugin:

- Has an independent directory and configuration.
- Implements standard plugin interfaces.
- Can subscribe to and handle events.
- Can register and provide capabilities.
- Has an independent lifecycle.

### Event

Events are the basic unit of internal system communication:

- **Message Event**: Received messages.
- **System Event**: System status changes.
- **Plugin Event**: Plugin lifecycle events.
- **Custom Event**: User-defined events.

### Adapter

Adapters bridge plugins and the framework:

- Responsible for plugin loading and initialization.
- Provide the plugin execution environment.
- Handle interactions between plugins and the framework.
- Support multiple plugin types.

### AI Config

AI Config defines AI behavior:

- **Global Config**: Global AI settings.
- **Group Config**: Group-level AI configuration.
- **User Config**: User-level AI configuration.
- **Preset Config**: Preset AI configuration templates.

### Memory

Memory stores conversation context:

- **Group Memory**: Group-level conversation history.
- **User Memory**: User-level conversation history.
- **Session Memory**: Single session context.

## Technology Stack

### Backend

- **Python 3.10+**: Primary development language.
- **FastAPI**: Web framework.
- **SQLAlchemy**: ORM framework.
- **asyncio**: Asynchronous programming.
- **Pydantic**: Data validation.

### Frontend

- **React**: UI framework.
- **TypeScript**: Type safety.
- **Tailwind CSS**: Style framework.
- **Vite**: Build tool.

### AI

- **OpenAI API**: LLM service.
- **MCP Protocol**: Model Context Protocol.
- **Vector Database**: Knowledge storage.
- **NLP Technology**: Natural Language Processing.

## Project Advantages

1. **Complete Ecosystem**: Provides a complete solution from development to deployment.
2. **Easy Extension**: The plugin system makes functional extension simple.
3. **High Performance**: Asynchronous architecture ensures high concurrency performance.
4. **Intelligence**: Deeply integrated AI provides intelligent interaction capabilities.
5. **Modern**: Uses the latest technology stack and best practices.
6. **Comprehensive Documentation**: Provides detailed documentation and examples.

## Scenarios

RuaBot is suitable for:

- **Group Chat Management**: Group content management, user management.
- **Intelligent Customer Service**: Auto-reply, Q&A.
- **Content Distribution**: News push, content recommendation.
- **Data Collection**: Data collection, statistical analysis.
- **Automated Tasks**: Scheduled tasks, automated workflows.
- **Entertainment Interaction**: Games, lucky draws, interactive features.

## Future Plans

RuaBot will continue to improve and expand:

- Support more LLM models.
- Enhance AI capabilities.
- Optimize performance.
- Improve documentation.
- Expand plugin ecosystem.
- Enhance security.

