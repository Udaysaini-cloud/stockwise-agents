"""StockWise Test Client Agent.

Used for local end-to-end verification of the Coordinator agent over the
Agent Chat Protocol (v0.3.0).
"""

import os
import certifi
from dotenv import load_dotenv

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

load_dotenv()

from uagents import Agent, Context
from uagents.resolver import RulesBasedResolver
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
)

# Configuration from environment
CLIENT_NAME = os.getenv("CLIENT_NAME", "stockwise-test-client")
CLIENT_SEED = os.getenv("CLIENT_SEED", "stockwise_client_test_seed_phrase_2026")
CLIENT_PORT = int(os.getenv("CLIENT_PORT", "8002"))

# Target coordinator address and local endpoint
COORDINATOR_ADDRESS = os.getenv(
    "COORDINATOR_ADDRESS",
    "agent1q2jq4rxh6wp56z7d09t23477y9gzc3uvr6j6tpdpl44r4rtzggd9jeflrev",
)
COORDINATOR_ENDPOINT = os.getenv("COORDINATOR_ENDPOINT", "http://127.0.0.1:8001/submit")

# Setup client with local resolver rules so it can route to coordinator without Almanac delays
resolver = RulesBasedResolver(
    rules={COORDINATOR_ADDRESS: COORDINATOR_ENDPOINT}
)

client = Agent(
    name=CLIENT_NAME,
    seed=CLIENT_SEED,
    port=CLIENT_PORT,
    endpoint=[f"http://127.0.0.1:{CLIENT_PORT}/submit"],
    resolve=resolver,
)


@client.on_event("startup")
async def send_hello(ctx: Context):
    """Send initial Hello message on startup to verify protocol response."""
    ctx.logger.info("=" * 60)
    ctx.logger.info(f"Client Agent address: {client.address}")
    ctx.logger.info(f"Target Coordinator:   {COORDINATOR_ADDRESS}")
    ctx.logger.info("Sending ChatMessage: 'Hello'...")
    ctx.logger.info("=" * 60)

    await ctx.send(
        COORDINATOR_ADDRESS,
        ChatMessage(
            content=[TextContent(type="text", text="Hello")],
        ),
    )


@client.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgement from coordinator."""
    ctx.logger.info(
        f"[ACK RECEIVED] From: {sender} | Acknowledged Msg ID: {msg.acknowledged_msg_id}"
    )


@client.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle ChatMessage response from coordinator."""
    # Acknowledge the coordinator's message
    await ctx.send(
        sender,
        ChatAcknowledgement(acknowledged_msg_id=msg.msg_id),
    )

    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(f"[RESPONSE RECEIVED] From: {sender}")
            ctx.logger.info(f"[CONTENT]: {item.text}")
            print("\n" + "=" * 60)
            print("PROTOCOL VERIFICATION SUCCESSFUL!")
            print(f"From:     {sender}")
            print(f"Message:  {item.text}")
            print("=" * 60 + "\n")


if __name__ == "__main__":
    print(f"Starting StockWise Test Client on port {CLIENT_PORT}...")
    client.run()
