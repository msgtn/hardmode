import pickle
import threading
import logging
from dataclasses import dataclass
from typing import Any, Callable

import zenoh

log = logging.getLogger(__name__)


@dataclass
class Message:
    topic: str
    data: Any


class MessageBus:
    """Pub/sub message bus backed by Zenoh."""

    def __init__(self, config: zenoh.Config | None = None):
        self._session = zenoh.open(config or zenoh.Config())
        self._subscribers: list[zenoh.Subscriber] = []
        self._closed = False

    def subscribe(self, topic: str, callback: Callable[[Message], None]):
        def _on_sample(sample: zenoh.Sample):
            if self._closed:
                return
            data = pickle.loads(sample.payload.to_bytes())
            callback(Message(topic=topic, data=data))

        sub = self._session.declare_subscriber(topic, _on_sample)
        self._subscribers.append(sub)

    def publish(self, topic: str, data: Any):
        if self._closed:
            return
        self._session.put(topic, pickle.dumps(data))

    def close(self):
        self._closed = True
        for sub in self._subscribers:
            sub.undeclare()
        self._session.close()


class Node:
    """Base class for all nodes. Each node runs in its own thread."""

    def __init__(self, name: str, bus: MessageBus):
        self.name = name
        self.bus = bus
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._running = False

    def subscribe(self, topic: str, callback: Callable[[Message], None]):
        self.bus.subscribe(topic, callback)

    def publish(self, topic: str, data: Any):
        self.bus.publish(topic, data)

    def start(self):
        self._running = True
        self._thread.start()
        log.info(f"[{self.name}] started")

    def stop(self):
        self._running = False

    def _run(self):
        """Override in subclasses. Must check self._running in loop."""
        raise NotImplementedError
