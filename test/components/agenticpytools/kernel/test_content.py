"""Unit tests for iopub message capture."""

from queue import Empty
from typing import cast

import pytest
from agenticpytools.kernel.content import capture
from jupyter_client import BlockingKernelClient

pytestmark = pytest.mark.kernel


def msg(msg_id, msg_type, content):
    return {
        "parent_header": {"msg_id": msg_id},
        "header": {"msg_type": msg_type},
        "content": content,
    }


class FakeKC:
    def __init__(self, messages):
        self.messages = list(messages)

    def get_iopub_msg(self, timeout=None):
        if not self.messages:
            raise Empty

        return self.messages.pop(0)


def fake_kc(messages) -> BlockingKernelClient:
    """A FakeKC typed as the client capture expects."""
    return cast(BlockingKernelClient, FakeKC(messages))


def test_capture_streams_result_and_idle():
    kc = fake_kc(
        [
            msg("id", "stream", {"name": "stdout", "text": "hello"}),
            msg("id", "stream", {"name": "stderr", "text": "oops"}),
            msg("id", "execute_result", {"data": {"text/plain": "6"}}),
            msg("id", "status", {"execution_state": "idle"}),
        ]
    )

    assert capture(kc, "id", 1) == (["hello"], ["oops"], {"text/plain": "6"}, None)


def test_capture_skips_foreign_msgs():
    kc = fake_kc(
        [
            msg("other", "stream", {"name": "stdout", "text": "ignored"}),
            msg("id", "stream", {"name": "stdout", "text": "hello"}),
            msg("id", "status", {"execution_state": "idle"}),
        ]
    )

    stdout, stderr, result, error = capture(kc, "id", 1)

    assert stdout == ["hello"]
    assert stderr == []
    assert result is None
    assert error is None


def test_capture_error_msg():
    kc = fake_kc(
        [
            msg("id", "error", {"traceback": ["l1", "l2"]}),
            msg("id", "status", {"execution_state": "idle"}),
        ]
    )

    assert capture(kc, "id", 1)[3] == "l1\nl2"


def test_capture_timeout():
    with pytest.raises(TimeoutError):
        capture(fake_kc([]), "id", 1)
