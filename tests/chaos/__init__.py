"""
Chaos Testing Module

Run chaos tests with:
    pytest tests/chaos/ -v --chaos-level=medium

Chaos Levels:
- low: Basic failure scenarios (timeouts, empty streams)
- medium: Worker kills, network delays, message corruption
- high: Resource exhaustion, concurrent conflicts
- extreme: All chaos scenarios + extended duration
"""
