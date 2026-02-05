# Bug Report: Voice Messages Losing Context

## Problem Description

When users send consecutive voice messages without using the "Reply" feature, each message creates a **new conversation tree** instead of continuing the existing conversation.

### Example Flow That Fails

1. User sends voice message: "Hazme un reporte"
   - Creates tree1 with root node msg1
   - Claude processes: "Voy a hacer tu reporte..." ✅

2. User sends another voice: "Dónde está mi reporte"
   - Creates **tree2** (separate!) with root node msg2  ❌
   - Claude says: "No sé de qué estás hablando" ❌

3. User sends another voice: "¿Por qué no me respondiste?"
   - Creates **tree3** (separate!) with root node msg3 ❌
   - Claude is confused ❌

### Expected Behavior

All 3 voice messages should be part of the same conversation, allowing Claude to remember the request for "hazme un reporte" and respond appropriately to follow-up questions.

## Root Cause

In `messaging/telegram.py`, when creating `IncomingMessage`:

```python
reply_to_message_id = (
    str(update.message.reply_to_message.message_id)
    if update.message.reply_to_message
    else None
)
```

If the user doesn't explicitly use "Reply" in Telegram, `reply_to_message_id` is `None`, and the handler treats it as a **completely new conversation**.

In `messaging/handler.py` lines 145-149:

```python
if parent_node_id and tree and status_msg_id:
    # Reply to existing node - add as child
    ...
elif status_msg_id:
    # New conversation - create new tree  ← THIS BRANCH EXECUTES
```

## Impact

- Users must use "Reply" for every message to maintain context
- Unnatural user experience
- Breaks expected conversational flow
- Each voice message starts fresh with no memory

## Proposed Solution

### Option 1: Recent Activity Detection (Recommended)

Automatically associate messages with the most recent active conversation from the same chat/user if within a time window (e.g., 10-15 minutes).

```python
# In handler.py
# Before creating a new tree, check for recent activity in this chat
if not parent_node_id:
    parent_node_id = await self._find_recent_active_node(incoming.chat_id, incoming.user_id)
```

### Option 2: Thread Mode

Add a "thread mode" setting where all messages in a chat are automatically added to the same tree until explicitly ended.

### Option 3: Hybrid Approach

- If message is a reply → use that parent
- Else if recent activity (last 10 min) in same chat → continue that conversation
- Else → new conversation

## Reproduction Steps

1. Start bot
2. Send voice message: "Hazme un reporte de ventas"
3. Wait for response
4. Send voice message (NOT using Reply): "Dónde está mi reporte"
5. Observe that Claude has no context

## Test Case

```python
# This fails currently because msg2 doesn't reference msg1
def test_consecutive_voice_messages():
    incoming1 = IncomingMessage(text="Hazme reporte", ...)
    # Process msg1 → creates tree1 → session_id = "abc"

    incoming2 = IncomingMessage(text="Dónde reporte", ...)
    # Process msg2 → creates tree2 → session_id = None (NEW!)

    # ASSERTION FAILS: session_id should be "abc" (forked from tree1)
    assert tree2.get_parent_session_id("msg2") == "abc"
```
