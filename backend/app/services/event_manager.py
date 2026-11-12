"""In-process pub/sub used to push replay ticks to websocket clients."""
from __future__ import annotations

import asyncio
from typing import Any


class EventManager:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()  # drop the oldest frame instead of stalling the clock
                except asyncio.QueueEmpty:  # pragma: no cover - defensive
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:  # pragma: no cover - defensive
                pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
