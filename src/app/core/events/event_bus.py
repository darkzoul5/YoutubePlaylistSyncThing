from __future__ import annotations

from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, Dict, List


EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class EventBus:
    """Simple async pub/sub event bus used by backend and (later) GUI."""

    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subs[event_name].append(handler)

    async def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        for h in list(self._subs.get(event_name, [])):
            await h(payload)
