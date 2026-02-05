"""Test that reproduces the voice message context loss bug."""

import pytest
from datetime import datetime, timezone
from messaging.models import IncomingMessage
from messaging.tree_data import MessageTree, MessageNode, MessageState
from messaging.handler import ClaudeMessageHandler
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.asyncio
async def test_consecutive_voice_messages_without_reply_lose_context():
    """
    Test demonstrating the bug:
    When a user sends voice messages consecutively WITHOUT using 'Reply',
    the second message does NOT get associated with the first message's tree.
    
    This test EXPECTS TO FAIL initially, demonstrating the bug.
    After implementing the fix, it should PASS.
    """
    # Setup mocks
    platform = Mock()
    platform.queue_send_message = AsyncMock(return_value="status_1")
    platform.queue_edit_message = AsyncMock()  # Add this for async edit method

    cli_manager = Mock()
    cli_manager.get_stats = Mock(return_value={"active_sessions": 0, "max_sessions": 10})

    # Mock the CLI session for async iteration
    mock_cli_session = Mock()
    mock_cli_session.start_task = AsyncMock(return_value=[])
    cli_manager.get_or_create_session = AsyncMock(
        return_value=(mock_cli_session, "session_123", False)
    )

    from messaging.session import SessionStore

    session_store = SessionStore(":memory:")
    handler = ClaudeMessageHandler(platform, cli_manager, session_store)
    
    # First voice message: "Hazme un reporte"
    incoming1 = IncomingMessage(
        text="Hazme un reporte",
        chat_id="chat_123",
        user_id="user_456",
        message_id="msg_1",
        platform="telegram",
    )
    
    await handler.handle_message(incoming1)
    
    # Mark first message as completed with session
    tree1 = handler.tree_queue.get_tree_for_node("msg_1")
    assert tree1 is not None, "Tree should exist for first message"
    
    node1 = tree1.get_node("msg_1")
    node1.session_id = "session_abc"
    node1.state = MessageState.COMPLETED
    node1.completed_at = datetime.now(timezone.utc)
    session_store.save_tree(tree1.root_id, tree1.to_dict())
    
    # Second voice message: "Dónde está mi reporte" 
    # IMPORTANT: No reply_to_message_id - simulating consecutive messages
    incoming2 = IncomingMessage(
        text="Dónde está mi reporte",
        chat_id="chat_123",  # Same chat
        user_id="user_456",  # Same user
        message_id="msg_2",
        platform="telegram",
        # NO reply_to_message_id - simulating natural consecutive messages
    )
    
    # Process second message
    await handler.handle_message(incoming2)
    
    # CHECK CONTEXT RETENTION
    tree2 = handler.tree_queue.get_tree_for_node("msg_2")
    assert tree2 is not None, "Tree should exist for second message"
    
    node2 = tree2.get_node("msg_2")
    
  # Verificar que el mensaje 2 es hijo del mensaje 1 (mismo árbol)
    assert node2.parent_id == "msg_1", (
        f"❌ FALLIDO: El segundo mensaje NO es hijo del primero. "
        f"Expected parent_id='msg_1', got parent_id='{node2.parent_id}'. "
        f"¡Esto significa que se perdió el contexto!"
    )

    # Éxito - los mensajes están correctamente enlazados
    print("✅ ÉXITO: Los mensajes de voz consecutivos mantienen el contexto!")


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_consecutive_voice_messages_without_reply_lose_context())
    except AssertionError as e:
        print(f"\n{'='*60}")
        print(f"BUG CONFIRMED:")
        print(f"{'='*60}")
        print(str(e))
        print(f"{'='*60}")
