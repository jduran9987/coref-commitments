"""Slack source adapter for message normalization.

This module provides SlackAdapter, which transforms raw Slack message data
from slack_messages.json into NormalizedMessage objects. The adapter strips
authoring metadata (_note fields) but preserves all messages, including filler,
to simulate real-world message streams with inherent noise.

Filler messages are kept to test the downstream LLM's ability to ignore
irrelevant messages on its own, without explicit filtering signals.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from coref_commitments.models.normalized import NormalizedMessage


class SlackAdapter:
    """Transforms raw Slack message data into normalized messages.

    Reads slack_messages.json, strips authoring metadata (_note fields),
    and emits a list of NormalizedMessage objects ready for downstream
    layers.
    """

    def __init__(self, slack_messages_path: str | Path) -> None:
        """Initialize the adapter with a path to slack_messages.json.

        Args:
            slack_messages_path: Path to the mock Slack source file.
        """
        self.slack_messages_path = Path(slack_messages_path)
        self._messages = self._load_messages()

    def _load_messages(self) -> list[dict[str, Any]]:
        """Load and parse slack_messages.json."""
        with open(self.slack_messages_path) as f:
            data = json.load(f)
        return data.get("messages", [])

    def adapt(self) -> list[NormalizedMessage]:
        """Transform raw Slack messages into normalized form.

        Returns:
            List of NormalizedMessage objects, sorted by timestamp.
            Filler messages (those with _note: "filler") are
            excluded.
        """
        normalized = []

        for msg in self._messages:
            normalized_msg = self._normalize_message(msg)

            if normalized_msg:
                normalized.append(normalized_msg)

        # Sort by timestamp for chronological ordering
        return sorted(normalized, key=lambda m: m.timestamp)

    def _normalize_message(self, msg: dict[str, Any]) -> NormalizedMessage | None:
        """Transform a single raw Slack message into NormalizedMessage.

        Args:
            msg: Raw message dict from slack_messages.json

        Returns:
            NormalizedMessage, or None if the message cannot be normalized.
        """
        msg_id = msg.get("msg_id")
        user_id = msg.get("user_id")
        text = msg.get("text")
        ts = msg.get("ts", "1970-01-01T00:00:00Z")
        channel = msg.get("channel")
        thread_ts = msg.get("thread_ts")

        # Validate required fields
        if not all([msg_id, user_id, text, ts, channel]):
            return None

        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError, AttributeError:
            return None

        # Build thread_id: channel:thread_ts if htis is a thread reply, else None
        thread_id = None
        if thread_ts:
            thread_id = f"{channel}:{thread_ts}"

        return NormalizedMessage(
            msg_id=msg_id,
            source="slack",
            sender_id=user_id,
            text=text,
            timstamp=timestamp,
            thread_id=thread_id,
            channel_or_ticket=channel,
            recipients=[],  # Slack has no cc/to; always empty
        )
