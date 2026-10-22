"""StockWise Coordinator Agent.

Implements the official Fetch.ai Innovation Lab Agent Chat Protocol (v0.3.0)
compatible with Agentverse Mailbox and ASI:One Chat.
"""

import os
import certifi
from dotenv import load_dotenv

# Ensure SSL certificates are properly located on macOS / UNIX
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

load_dotenv()

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

# Configuration from environment
COORDINATOR_NAME = os.getenv("COORDINATOR_NAME", "stockwise-coordinator")
COORDINATOR_SEED = os.getenv("COORDINATOR_SEED", "stockwise_coordinator_local_dev_seed_phrase_2026")
COORDINATOR_PORT = int(os.getenv("COORDINATOR_PORT", "8001"))
AGENT_MAILBOX_KEY = os.getenv("AGENT_MAILBOX_KEY", "").strip()
USE_MAILBOX = os.getenv("AGENT_MAILBOX_ENABLED", "false").lower() in ("true", "1", "yes") or bool(AGENT_MAILBOX_KEY)
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "").strip()

# Initialize the Agent
if USE_MAILBOX:
    # Mailbox configuration for Agentverse & ASI:One discovery
    # In uagents 0.25.5, mailbox=True uses Agentverse mailbox endpoint
    coordinator = Agent(
        name=COORDINATOR_NAME,
        seed=COORDINATOR_SEED,
        port=COORDINATOR_PORT,
        mailbox=True,
        publish_agent_details=True,
    )
else:
    # Local HTTP endpoint configuration for local pair-testing
    coordinator = Agent(
        name=COORDINATOR_NAME,
        seed=COORDINATOR_SEED,
        port=COORDINATOR_PORT,
        endpoint=[f"http://127.0.0.1:{COORDINATOR_PORT}/submit"],
        publish_agent_details=True,
    )

# Protocol declaration using official chat_protocol_spec (AgentChatProtocol 0.3.0)
chat_protocol = Protocol(spec=chat_protocol_spec)


def generate_response(user_text: str) -> str:
    """Generate response for incoming user text.

    Kept independent of ASI1 credentials for Hello and base queries (Milestone 1, Rule 5).
    """
    cleaned = user_text.strip().lower()

    # Rule 5: Keep initial Hello response independent of ASI1 API credentials
    if not cleaned or "hello" in cleaned or "hi" in cleaned or "help" in cleaned:
        return (
            "Hello! I am StockWise Coordinator, your autonomous inventory "
            "and procurement assistant. Send me an inventory query or restock request."
        )

    # Optional ASI:One LLM reasoning if API key is provided
    if ASI1_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(
                base_url="https://api.asi1.ai/v1",
                api_key=ASI1_API_KEY,
            )
            r = client.chat.completions.create(
                model="asi1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are StockWise Coordinator, an autonomous inventory and procurement agent. "
                            "Assist users with supply chain queries and purchase approvals."
                        ),
                    },
                    {"role": "user", "content": user_text},
                ],
                max_tokens=512,
            )
            return str(r.choices[0].message.content)
        except Exception as err:
            return (
                f"StockWise Coordinator received: '{user_text}'. "
                f"(Autonomous local engine active; ASI:One reasoning fallback: {err})"
            )

    return f"StockWise Coordinator received: '{user_text}'. Autonomous local engine ready."


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming ChatMessage, acknowledge immediately, and reply with TextContent."""
    # 1. Acknowledge the message (mandatory per Agent Chat Protocol 0.3.0)
    await ctx.send(
        sender,
        ChatAcknowledgement(acknowledged_msg_id=msg.msg_id),
    )
    ctx.logger.info(f"Acknowledged message {msg.msg_id} from {sender}")

    # 2. Extract text content from payload blocks
    incoming_text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            incoming_text += item.text

    ctx.logger.info(f"Received query from {sender}: {incoming_text}")
    reply_text = generate_response(incoming_text)

    # 3. Send response back to sender
    await ctx.send(
        sender,
        ChatMessage(
            content=[
                TextContent(type="text", text=reply_text),
                EndSessionContent(type="end-session"),
            ]
        ),
    )
    ctx.logger.info(f"Sent reply to {sender}: {reply_text[:60]}...")


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements from counterpart agents."""
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message ID: {msg.acknowledged_msg_id}"
    )


# Include protocol in agent and publish manifest for Agentverse / ASI:One discovery
coordinator.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    print("=" * 60)
    print(f"StockWise Coordinator Agent")
    print(f"Address:  {coordinator.address}")
    print(f"Port:     {COORDINATOR_PORT}")
    print(f"Mailbox:  {'Enabled' if USE_MAILBOX else 'Disabled (Local HTTP endpoint)'}")
    print("=" * 60)
    coordinator.run()
