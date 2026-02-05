import json

import pytest

from services.redis.client import RedisStreamsClient


class DummyRedis:
    def __init__(self):
        self.added = None

    def xadd(self, stream, payload, maxlen=None, approximate=None):
        self.added = (stream, payload, maxlen, approximate)
        return "0-1"

    def xread(self, streams, count=None, block=None):
        return [
            (list(streams.keys())[0], [("1-0", {"payload": json.dumps({"a": 1}), "metadata": "{}"})])
        ]

    def xgroup_create(self, stream, group, id="$", mkstream=True):
        raise Exception("BUSYGROUP Consumer Group name already exists")


def test_chan_namespacing_rules():
    client = RedisStreamsClient.__new__(RedisStreamsClient)
    client.ns = "tenant"

    assert client._chan("tenant:manager:tasks") == "tenant:manager:tasks"
    assert client._chan("tenant:outreach:auto_send") == "tenant:outreach:auto_send"
    assert client._chan("manager:tasks") == "tenant:manager:tasks"
    assert client._chan("custom:stream") == "tenant:custom:stream"


def test_xadd_encodes_payload_fields():
    client = RedisStreamsClient.__new__(RedisStreamsClient)
    client.ns = "tenant"
    client.client = DummyRedis()

    msg_id = client.xadd("manager:tasks", {"payload": {"a": 1}, "id": "x"}, maxlen=5)

    assert msg_id == "0-1"
    stream, payload, maxlen, approximate = client.client.added
    assert stream == "tenant:manager:tasks"
    assert payload["payload"] == json.dumps({"a": 1})
    assert payload["id"] == "x"
    assert maxlen == 5
    assert approximate is False


def test_xread_decodes_selected_fields():
    client = RedisStreamsClient.__new__(RedisStreamsClient)
    client.ns = "tenant"
    client.client = DummyRedis()

    result = client.xread({"manager:results": "0"})
    _, entries = result[0]
    _, fields = entries[0]
    assert isinstance(fields["payload"], dict)
    assert fields["payload"]["a"] == 1


def test_xgroup_create_busygroup_returns_false():
    client = RedisStreamsClient.__new__(RedisStreamsClient)
    client.ns = "tenant"
    client.client = DummyRedis()

    assert client.xgroup_create("manager:tasks", "workers") is False