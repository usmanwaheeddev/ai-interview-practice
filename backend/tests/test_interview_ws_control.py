import json

import pytest
from fastapi import WebSocketDisconnect

from app.ws.interview import wait_for_session_end


class FakeWebSocket:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = iter(messages)

    async def receive(self) -> dict:
        return next(self.messages)


async def test_ignores_queued_microphone_frames_until_session_end() -> None:
    websocket = FakeWebSocket(
        [
            {"type": "websocket.receive", "bytes": b"stale audio"},
            {"type": "websocket.receive", "bytes": b"more stale audio"},
            {
                "type": "websocket.receive",
                "text": json.dumps({"type": "session.end"}),
            },
        ]
    )

    await wait_for_session_end(websocket)  # type: ignore[arg-type]


async def test_disconnect_is_not_swallowed_as_audio() -> None:
    websocket = FakeWebSocket([{"type": "websocket.disconnect"}])

    with pytest.raises(WebSocketDisconnect):
        await wait_for_session_end(websocket)  # type: ignore[arg-type]
