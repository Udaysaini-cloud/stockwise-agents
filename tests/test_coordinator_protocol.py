"""Tests for Milestone 1 - Coordinator Agent and Chat Protocol."""

import pytest
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from agents.coordinator import (
    coordinator,
    chat_protocol,
    generate_response,
    COORDINATOR_SEED,
)


def test_chat_protocol_specification():
    """Verify that chat protocol specification matches official AgentChatProtocol 0.3.0."""
    assert chat_protocol_spec.name == "AgentChatProtocol"
    assert chat_protocol_spec.version == "0.3.0"


def test_coordinator_deterministic_address():
    """Verify that coordinator has a valid, deterministic Fetch.ai address."""
    assert coordinator.address.startswith("agent1")
    # Verify address matches deterministic seed
    assert coordinator.address == "agent1q2jq4rxh6wp56z7d09t23477y9gzc3uvr6j6tpdpl44r4rtzggd9jeflrev"


def test_hello_response_independent_of_asi1():
    """Verify Hello response functions deterministically without ASI1 credentials (Rule 5)."""
    # Test lowercase
    resp1 = generate_response("hello")
    assert "StockWise Coordinator" in resp1
    assert "autonomous inventory" in resp1

    # Test titlecase
    resp2 = generate_response("Hello")
    assert "StockWise Coordinator" in resp2

    # Test hi greeting
    resp3 = generate_response("hi there")
    assert "StockWise Coordinator" in resp3

    # Test empty query
    resp4 = generate_response("")
    assert "StockWise Coordinator" in resp4


def test_chat_message_creation():
    """Verify ChatMessage with TextContent can be constructed and validated."""
    content = [TextContent(type="text", text="Hello StockWise")]
    msg = ChatMessage(content=content)
    assert msg.msg_id is not None
    assert msg.timestamp is not None
    assert len(msg.content) == 1
    assert isinstance(msg.content[0], TextContent)
    assert msg.content[0].text == "Hello StockWise"


def test_chat_acknowledgement_creation():
    """Verify ChatAcknowledgement matches schema and acknowledges correct msg_id."""
    content = [TextContent(type="text", text="Hello")]
    msg = ChatMessage(content=content)
    ack = ChatAcknowledgement(acknowledged_msg_id=msg.msg_id)
    assert ack.acknowledged_msg_id == msg.msg_id
    assert ack.timestamp is not None


def test_protocol_verification_passed():
    """Verify that chat protocol satisfies all spec requirements with handlers implemented."""
    assert chat_protocol.verify() is True
