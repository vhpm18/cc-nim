# Voice Message Context Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable automatic context retention for consecutive voice/text messages in Telegram by associating messages with recent active conversations instead of requiring explicit "Reply" usage.

**Architecture:** Add a new `_find_recent_active_node()` method to `ClaudeMessageHandler` that searches the tree queue for the most recent activity from the same chat/user within a configurable time window (default 10 minutes). Modify `handle_message()` to check for recent activity when no explicit reply is detected.

**Tech Stack:** Python 3.10, asyncio, dataclasses, existing tree queue structure. New config: `VOICE_CONTEXT_WINDOW_MINUTES` environment variable.

---

## Configuration Changes

### Before Implementation

Copy `.env.example` to `.env` (if you haven't already) and add:

```bash
cp .env.example .env
```

Then add to `.env`:
```
# Voice message context retention (minutes)
# Set to 0 to disable automatic context detection
VOICE_CONTEXT_WINDOW_MINUTES=10
```

---

## Task 1: Add Configuration Setting

**Files:**
- Modify: `config/settings.py:1-50` (need to see full file first)

**Step 1: Read config/settings.py**

```bash
uv run head -30 config/settings.py
```

**Step 2: Add VOICE_CONTEXT_WINDOW_MINUTES setting**

```python
# Add to config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # ... existing settings ...
    voice_context_window_minutes: int = 10  # Add this line
```

**Step 3: Commit config**

```bash
git add config/settings.py
git commit -m "config: add VOICE_CONTEXT_WINDOW_MINUTES setting"
```

---

## Task 2: Add Recent Activity Detection Method

**Files:**
- Modify: `messaging/handler.py:37-610` (ClaudeMessageHandler class)

**Step 1: Add `_find_recent_active_node()` method after initialize()**

```python
async def _find_recent_active_node(
    self, chat_id: str, user_id: str, max_age_minutes: int = 10
) -> Optional[MessageNode]:
    """
    Find the most recent active node from the same chat/user.

    Args:
        chat_id: The chat identifier
        user_id: The user identifier
        max_age_minutes: Maximum age in minutes to consider

    Returns:
        The most recent active MessageNode or None
    """
    if max_age_minutes <= 0:
        return None

    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    most_recent: Optional[MessageNode] = None
    most_recent_time: Optional[datetime] = None

    # Iterate through all trees to find matching recent activity
    for tree in self.tree_queue._trees.values():
        # Check if this tree is for the same chat
        root = tree.get_root()
        if root.incoming.chat_id == chat_id:
            # Check root node
            if root.incoming.user_id == user_id:
                if root.completed_at and root.completed_at > cutoff_time:
                    if not most_recent_time or root.completed_at > most_recent_time:
                        most_recent = root
                        most_recent_time = root.completed_at

            # Check child nodes recursively
            for node_id in root.children_ids:
                node = tree.get_node(node_id)
                if node and node.incoming.user_id == user_id:
                    if node.completed_at and node.completed_at > cutoff_time:
                        if not most_recent_time or node.completed_at > most_recent_time:
                            most_recent = node
                            most_recent_time = node.completed_at

    if most_recent:
        logger.info(
            f"Found recent active node {most_recent.node_id} from "
            f"{most_recent_time} for chat {chat_id}"
        )

    return most_recent
```

**Step 2: Add imports at top of handler.py**

```python
from datetime import datetime, timezone, timedelta  # Add timedelta
```

**Step 3: Commit method**

```bash
git add messaging/handler.py
git commit -m "feat: add _find_recent_active_node() for context detection"
```

---

## Task 3: Modify handle_message() to Use Recent Activity

**Files:**
- Modify: `messaging/handler.py:94-113` (reply detection section)

**Step 1: Modify reply detection logic**

```python
# Find parent node and tree
parent_node_id = None
tree = None

if incoming.is_reply() and incoming.reply_to_message_id:
    # Original logic for explicit replies
    reply_id = incoming.reply_to_message_id
    tree = self.tree_queue.get_tree_for_node(reply_id)
    if tree:
        parent_node_id = self.tree_queue.resolve_parent_node_id(reply_id)
        if parent_node_id:
            logger.info(f"Found tree for explicit reply, parent node: {parent_node_id}")
        else:
            logger.warning(
                f"Reply to {incoming.reply_to_message_id} found tree but no valid parent node"
            )
            tree = None
elif incoming.is_reply():
    # Explicit reply but message_id None (edge case)
    logger.debug(f"Message {incoming.message_id} marked as reply but no reply_to_message_id")

# NEW: Check for recent activity if no explicit reply
if not parent_node_id and not tree and incoming.chat_id:
    from config import settings
    max_age = settings.voice_context_window_minutes

    if max_age > 0:
        logger.debug(
            f"No explicit reply found, checking recent activity for chat "
            f"{incoming.chat_id} (window: {max_age} minutes)"
        )
        recent_node = await self._find_recent_active_node(
            incoming.chat_id, incoming.user_id, max_age_minutes=max_age
        )
        if recent_node:
            parent_node_id = recent_node.node_id
            tree = self.tree_queue.get_tree_for_node(parent_node_id)
            if tree:
                logger.info(
                    f"Found recent active node {parent_node_id} for chat "
                    f"{incoming.chat_id}, continuing conversation"
                )
            else:
                logger.warning(f"Recent node {parent_node_id} found but no tree")
                parent_node_id = None
```

**Step 2: Commit message handling change**

```bash
git add messaging/handler.py
git commit -m "feat: use recent activity detection for voice message context"
```

---

## Task 4: Write Tests

**Files:**
- Create: `tests/messaging/test_voice_context.py`

**Step 1: Create test file**

```python
"""Tests for voice message context retention."""

import pytest
from datetime import datetime, timezone, timedelta
from messaging.models import IncomingMessage
from messaging.tree_data import MessageTree, MessageNode, MessageState
from messaging.handler import ClaudeMessageHandler
from unittest.mock import Mock, AsyncMock


@pytest.mark.asyncio
async def test_consecutive_voice_messages_maintain_context():
    """Test that consecutive voice messages without 'Reply' maintain context."""
    # Setup mocks
    platform = Mock()
    platform.queue_send_message = AsyncMock(return_value="status_1")

    cli_manager = Mock()
    cli_manager.get_or_create_session = AsyncMock(return_value=(Mock(), "session_123", False))

    from messaging.session import SessionStore
    from config import settings

    settings.voice_context_window_minutes = 10

    session_store = SessionStore(":memory:")
    handler = ClaudeMessageHandler(platform, cli_manager, session_store)

    # First voice message (creates tree)
    incoming1 = IncomingMessage(
        text="Hazme un reporte",
        chat_id="chat_123",
        user_id="user_456",
        message_id="msg_1",
        platform="telegram",
    )

    # Simulate first message processing completed
    await handler.handle_message(incoming1)

    # Get the tree
    tree = handler.tree_queue.get_tree_for_node("msg_1")
    assert tree is not None

    # Mark first node as completed with session
    node1 = tree.get_node("msg_1")
    node1.session_id = "session_abc"
    node1.state = MessageState.COMPLETED
    node1.completed_at = datetime.now(timezone.utc)

    # Save tree
    session_store.save_tree(tree.root_id, tree.to_dict())

    # Second voice message (NOT using reply, but same chat)
    incoming2 = IncomingMessage(
        text="Donde esta mi reporte",
        chat_id="chat_123",  # Same chat
        user_id="user_456",  # Same user
        message_id="msg_2",
        platform="telegram",
        # NO reply_to_message_id - simulating consecutive messages
    )

    # Mock finding recent node
    with patch.object(handler, '_find_recent_active_node') as mock_find:
        mock_find.return_value = node1

        await handler.handle_message(incoming2)

        # Verify it found recent activity
        mock_find.assert_called_once_with("chat_123", "user_456", max_age_minutes=10)

    # Get second tree
    tree2 = handler.tree_queue.get_tree_for_node("msg_2")
    assert tree2 is not None

    # Verify second node is a child of first (maintained context)
    node2 = tree2.get_node("msg_2")
    assert node2.parent_id == "msg_1"

    # Verify session_id was passed correctly
    assert node2.session_id == "session_abc"


@pytest.mark.asyncio
async def test_recent_activity_disabled():
    """Test that setting VOICE_CONTEXT_WINDOW_MINUTES=0 disables detection."""
    from config import settings

    settings.voice_context_window_minutes = 0

    session_store = SessionStore(":memory:")
    handler = ClaudeMessageHandler(Mock(), Mock(), session_store)

    # Call method with disabled setting
    result = await handler._find_recent_active_node("chat_123", "user_456")

    assert result is None


@pytest.mark.asyncio
async def test_no_recent_activity_found():
    """Test when no recent activity exists."""
    session_store = SessionStore(":memory:")
    handler = ClaudeMessageHandler(Mock(), Mock(), session_store)

    # No trees exist
    result = await handler._find_recent_active_node("chat_123", "user_456", max_age_minutes=10)

    assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/messaging/test_voice_context.py::test_consecutive_voice_messages_maintain_context -v
```

**Expected output:**
```
tests/messaging/test_voice_context.py::test_consecutive_voice_messages_maintain_context FAILED
FAILED: AttributeError: 'ClaudeMessageHandler' object has no attribute '_find_recent_active_node'
```

**Step 3: Implement minimal code**

Implement the code from Task 1-3

**Step 4: Run tests again**

```bash
uv run pytest tests/messaging/test_voice_context.py -v
```

**Expected output:**
```
tests/messaging/test_voice_context.py::test_consecutive_voice_messages_maintain_context PASSED
tests/messaging/test_voice_context.py::test_recent_activity_disabled PASSED
tests/messaging/test_voice_context.py::test_no_recent_activity_found PASSED
3 passed
```

**Step 5: Commit tests**

```bash
git add tests/messaging/test_voice_context.py
git commit -m "test: add tests for voice message context retention"
```

---

## Task 5: Update Configuration Documentation

**Files:**
- Modify: `.env.example`

**Step 1: Add environment variable to .env.example**

```bash
echo "" >> .env.example
echo "# Voice message context retention (minutes)" >> .env.example
echo "# Set to 0 to disable automatic context detection" >> .env.example
echo "VOICE_CONTEXT_WINDOW_MINUTES=10" >> .env.example
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add VOICE_CONTEXT_WINDOW_MINUTES to example config"
```

---

## Task 6: Manual Testing

**Step 1: Restart the bot with new config**

```bash
# Edit .env
echo "VOICE_CONTEXT_WINDOW_MINUTES=10" >> .env

# Restart the server
uv run uvicorn server:app --host 0.0.0.0 --port 8082 &
```

**Step 2: Test scenario from bug report**

```bash
# Send voice message 1: "Hazme un reporte"
# Expected: Creates new tree, responds "Voy a hacer tu reporte..."

# Wait 30 seconds
# Send voice message 2 (NOT using Reply): "Dónde está mi reporte"
# Expected: Finds recent activity, continues conversation, responds with report
```

**Step 3: Verify logs show context detection**

```bash
tail -f app.log | grep -E "(Found recent active node|continuing conversation)"
```

**Expected log output:**
```
Found recent active node msg_1 from 2026-02-04T10:30:15 for chat 123456
continuing conversation
```

**Step 4: Verify context maintained**

Second voice message should reference the first request and provide the report.

---

## Summary

After completing these 6 tasks, you will have:

1. ✅ Configurable time window for context retention (`.env`)
2. ✅ Automatic detection of recent conversations
3. ✅ Voice messages maintain context without "Reply"
4. ✅ Full test coverage for the feature
5. ✅ Updated documentation
6. ✅ Verified working with manual tests

The user's original problem will be resolved:
- **Before**: Voice messages 1 & 2 → separate trees → no context
- **After**: Voice messages 1 & 2 → same tree → context maintained ✅
