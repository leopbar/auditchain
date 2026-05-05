"""In-memory event publisher using asyncio queues.

Allows the audit background tasks to push events that are then consumed 
by SSE subscribers in real-time.
"""

import asyncio
import time
from typing import Dict, Optional

from auditchain.core.logging import get_logger
from auditchain.api.events.schemas import AuditEventBase

logger = get_logger(__name__)

MAX_QUEUE_SIZE = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour

class EventPublisher:
    """Singleton publisher that manages per-audit-run event queues."""
    
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue[Optional[AuditEventBase]]] = {}
        self._last_activity: Dict[str, float] = {}

    async def publish(self, event: AuditEventBase):
        """Publishes an event to the queue associated with the audit run_id."""
        run_id = event.run_id
        
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
            
        self._last_activity[run_id] = time.time()
        queue = self._queues[run_id]
        
        try:
            # Try to put the event with a timeout to avoid blocking the audit
            await asyncio.wait_for(queue.put(event), timeout=5.0)
            logger.info("event_published", run_id=run_id, event_type=event.event_type)
        except asyncio.TimeoutError:
            logger.warning("publish_queue_full", run_id=run_id, event_type=event.event_type)
        except Exception as e: 
            logger.error("publish_failed", run_id=run_id, error=str(e))

    async def publish_raw(self, stream_id: str, event: object):
        """Publishes any event (including ingestion events) to a named queue.
        
        Unlike publish(), this accepts an arbitrary stream_id rather than
        extracting run_id from the event. This allows ingestion events
        (which use ingestion_id instead of run_id) to share the same
        queue infrastructure.
        """
        if stream_id not in self._queues:
            self._queues[stream_id] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
            
        self._last_activity[stream_id] = time.time()
        queue = self._queues[stream_id]
        
        try:
            await asyncio.wait_for(queue.put(event), timeout=5.0)
            event_type = getattr(event, "event_type", "unknown")
            logger.info("event_published", stream_id=stream_id, event_type=event_type)
        except asyncio.TimeoutError:
            logger.warning("publish_queue_full", stream_id=stream_id)
        except Exception as e:
            logger.error("publish_failed", stream_id=stream_id, error=str(e))

    async def close(self, run_id: str):
        """Signals the end of a stream for a specific run_id by putting a sentinel."""
        if run_id in self._queues:
            try:
                await asyncio.wait_for(self._queues[run_id].put(None), timeout=5.0)
                logger.info("queue_closed", run_id=run_id)
            except Exception as e:
                logger.error("queue_close_failed", run_id=run_id, error=str(e))

    def get_queue(self, run_id: str) -> asyncio.Queue[Optional[AuditEventBase]]:
        """Retrieves or creates a queue for a specific run_id for subscribers."""
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
            
        self._last_activity[run_id] = time.time()
        return self._queues[run_id]

    async def cleanup_stale_queues(self, max_age_seconds: int = DEFAULT_TTL_SECONDS):
        """Removes queues that haven't seen activity for a long time."""
        now = time.time()
        to_delete = [
            run_id for run_id, last_time in self._last_activity.items()
            if now - last_time > max_age_seconds
        ]
        
        for run_id in to_delete:
            self._queues.pop(run_id, None)
            self._last_activity.pop(run_id, None)
            
        if to_delete:
            logger.info("stale_queues_cleaned", count=len(to_delete))

# Global singleton instance management
_publisher_instance: Optional[EventPublisher] = None

def get_publisher() -> EventPublisher:
    """Returns the global EventPublisher singleton."""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = EventPublisher()
    return _publisher_instance
