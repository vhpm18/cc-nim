# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cc-nim** is a FastAPI proxy service that translates Claude Code CLI's Anthropic API requests to NVIDIA NIM format. It enables using Claude Code for free with NVIDIA's API (40 requests/minute) and includes Telegram bot integration for remote control.

## Development Commands

### Setup and Running
```bash
# Install dependencies
uv sync

# Run the server
uv run uvicorn server:app --host 0.0.0.0 --port 8082

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_api.py
```

### Configuration
Copy `.env.example` to `.env` and configure:
- `NVIDIA_NIM_API_KEY`: Required - get from build.nvidia.com/settings/api-keys
- `MODEL`: Default model to use (default: `moonshotai/kimi-k2-thinking`)
- `TELEGRAM_BOT_TOKEN`: Optional - for Telegram integration
- `CLAUDE_WORKSPACE`: Directory for agent workspace (default: `./agent_workspace`)

## Architecture

### Core Components

**API Layer** (`/api/`)
- `app.py`: FastAPI application with lifespan management
- `routes.py`: API endpoints - `/v1/messages`, `/v1/count_tokens`, `/health`, `/stop`
- `models.py`: Pydantic models matching Anthropic API structures
- `request_utils.py`: Request optimizations (token counting, quota mock)

**Provider Layer** (`/providers/`)
- Abstraction layer for AI providers (NVIDIA NIM supported)
- `nvidia_nim.py`: Converts Anthropic requests to OpenAI format for NVIDIA NIM
- `rate_limit.py`: Global rate limiting for NVIDIA API (40 req/min)
- Handles request/response conversion and error mapping

**CLI Session Management** (`/cli/`)
- `session.py`: Manages individual Claude Code CLI subprocesses
- `manager.py`: Pool manager supporting up to 10 concurrent CLI sessions
- `parser.py`: Parses CLI events (thinking, tool calls, results)

**Telegram Integration** (`/messaging/`)
- `telegram.py`: Telegram bot adapter
- `handler.py`: Handles incoming messages, creates tree-structured conversations
- `tree_queue.py`: Tree-based message queue for conversation threading
- `event_parser.py`: Parses CLI events and formats for Telegram

### Request Flow

1. Claude Code sends Anthropic API request → `/v1/messages`
2. API routes: Convert to NVIDIA NIM format via `NvidiaNimProvider`
3. Provider: Make OpenAI-compatible request to NVIDIA NIM API
4. Response: Convert back to Anthropic format and return to CLI
5. CLI executes tools locally in `agent_workspace/`

### Telegram Message Flow

1. User sends message via Telegram
2. `MessageHandler` creates task in tree queue
3. CLI manager spawns session for task
4. As CLI generates events, they update tree structure
5. Status messages are updated/edited as task progresses

## Testing

- **Framework**: pytest with pytest-asyncio
- **Coverage**: 24 test files across all modules
- **Key test files**:
  - `test_api.py`: API endpoint tests
  - `test_nvidia_nim.py`: Provider conversion logic
  - `test_cli.py`: CLI session management
  - `test_messaging.py`: Telegram integration
  - `test_tree_queue.py`: Tree queueing logic

## Key Implementation Details

### Provider System
- To add a new provider: Extend `BaseProvider` in `/providers/base.py`
- Must implement: `complete()`, `stream_response()`, `convert_response()`
- Rate limiting is handled per-provider

### Message Handling
- Tree-based queue maintains conversation hierarchy
- Each task creates tree nodes for messages
- Status updates are tracked and displayed
- Supports multiple concurrent conversations

### Optimizations
- `FAST_PREFIX_DETECTION=true`: Intercepts command prefix requests
- `ENABLE_NETWORK_PROBE_MOCK=true`: Mocks quota checks for speed
- `ENABLE_TITLE_GENERATION_SKIP=true`: Avoids unnecessary title generation

### Environment Variables (Key)
- `MAX_CLI_SESSIONS=10`: Maximum concurrent CLI sessions
- `MESSAGING_RATE_LIMIT=1`: Telegram messages per second
- `NVIDIA_NIM_RATE_LIMIT=40`: NVIDIA API requests per minute
- `ALLOWED_DIR`: Restricts agent directory access
- All variables in `.env.example` can be adjusted
