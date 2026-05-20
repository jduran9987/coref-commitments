"""Data models for normalized messages.

This module defines NormalizedMessage, the common output shape for all source
adapters (Slack, Email, Linear). By normalizing across sources, downstream
layers (identity resolver, coreference resolver, commitment extractor) remain
decoupled from source-specific details.

NormalizedMessage is a Pydantic v2 model suitable for external validation
and serialization.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedMessage(BaseModel):
    """Common message shape output by all source adapters (Slack, Email, Linear).

    Fields are minimal and source-agnostic to keep downstream layers decoupled
    from source-specific details.
    """

    model_config = ConfigDict(frozen=False)

    msg_id: str = Field(description="Unique message identifier across all sources.")
    source: Literal["slack", "email", "linear"] = Field(
        description="Origin of the message."
    )
    sender_id: str = Field(
        description="Pre-lookup sender id (Slack: user_id, Email: "
            "email address, Linear: handle)"
    )
    text: str = Field(description="Message body text")
    timestamp: datetime = Field(..., description="When the message was sent")
    thread_id: str | None = Field(
        None,
        description="For grouping related messages within a conversation"
    )
    channel_or_ticket: str = Field(description="Where the message lives")
    recipients: list[str] = Field(
        default_factory=list,
        description="For email cc/to; empty for Slack and Linear"
    )
