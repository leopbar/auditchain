"""Event subscriber for streaming audit progress via SSE.

Handles the asynchronous generator logic to yield events from internal 
queues to HTTP clients using the Server-Sent Events protocol.
"""

import asyncio
import json
from typing import AsyncIterator

from auditchain.core.logging import get_logger
from auditchain.api.events.schemas import event_to_sse
from auditchain.api.events.publisher import get_publisher

logger = get_logger(__name__)

async def subscribe_to_audit(run_id: str) -> AsyncIterator[str]:
    """Asynchronous generator that produces SSE events for a specific run_id.
    
    Yields strings formatted according to the SSE protocol.
    Closes when a sentinel (None) is received or an error occurs.
    """
    publisher = get_publisher()
    queue = publisher.get_queue(run_id)
    
    logger.info("subscriber_connected", run_id=run_id)
    
    # Send initial connection confirmation
    yield f"event: stream_opened\ndata: {json.dumps({'run_id': run_id})}\n\n"
    
    try:
        while True:
            try:
                # Wait for next event with a heartbeat timeout
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                
                if event is None:  # End of stream sentinel
                    yield "event: stream_closed\ndata: {}\n\n"
                    logger.info("subscriber_stream_closed_by_publisher", run_id=run_id)
                    break
                
                yield event_to_sse(event)
                
            except asyncio.TimeoutError:
                # Send heartbeat to keep the connection alive
                yield ": heartbeat\n\n"
                
    except asyncio.CancelledError:
        logger.info("subscriber_disconnected", run_id=run_id)
    except Exception as e:
        logger.error("subscriber_error", run_id=run_id, error=str(e))
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    finally:
        logger.info("subscriber_completed", run_id=run_id)
