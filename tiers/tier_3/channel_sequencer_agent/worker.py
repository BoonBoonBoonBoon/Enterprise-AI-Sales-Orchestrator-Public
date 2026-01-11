"""Synchronous worker wrapper for ChannelSequencerAgent."""
from __future__ import annotations

from typing import Dict, Any

from tiers.tier_3.channel_sequencer_agent.channel_sequencer_agent import ChannelSequencerAgent


def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent = ChannelSequencerAgent()
    return agent.build_sequence(payload)
