import pytest

from ai_engine.status_indicator import StatusIndicator, exchange


class SerialFixture:
    def __init__(self, *, failure=False):
        self.failure = failure
        self.replies = []

    def write(self, packet):
        prefix, request_id, command, *value = packet.decode().split()
        assert prefix == "LEO"
        state = value[0] if value else "IDLE"
        self.replies.extend([b"unrelated startup message\n", f"LEO {request_id} {command} 1.0.0 {state} OK\n".encode()])

    def read_until(self, *_):
        if self.failure:
            raise OSError("disconnected")
        return self.replies.pop(0) if self.replies else b""


def test_serial_acknowledgments_match_request_and_state():
    port = SerialFixture()
    assert exchange(port, "PING") == "IDLE"
    assert exchange(port, "SET_STATUS", "AWAITING_CAPTURE") == "AWAITING_CAPTURE"
    assert exchange(port, "ALL_OFF") == "IDLE"


def test_serial_timeout_and_disconnect_do_not_claim_availability():
    with pytest.raises(TimeoutError):
        exchange(SerialFixture(), "PING", timeout=0)
    with pytest.raises(OSError, match="disconnected"):
        exchange(SerialFixture(failure=True), "PING")
    assert StatusIndicator(None).available is False
