"""Event system infrastructure."""

from myao2.infrastructure.events.dispatcher import EventDispatcher, event_handler
from myao2.infrastructure.events.loop import EventLoop
from myao2.infrastructure.events.queue import EventQueue
from myao2.infrastructure.events.scheduler import EventScheduler

__all__ = [
    "EventDispatcher",
    "EventLoop",
    "EventQueue",
    "EventScheduler",
    "event_handler",
]
