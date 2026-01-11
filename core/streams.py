def assert_agents_stream(stream_name: str) -> None:
    """
    Ensure a given stream name targets Tier 3 agent streams only.

    Allowed pattern: contains ":agents:" segment. This protects Tier 2
    orchestrators from accidentally publishing to other orchestrators or
    manager streams (horizontal comms).

    Raises ValueError if the stream does not include the agents segment.
    """
    if ":agents:" not in str(stream_name):
        raise ValueError(
            f"Tier 2 can only publish to agent streams; invalid stream: {stream_name}"
        )
