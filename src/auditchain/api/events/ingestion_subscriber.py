"""Event subscriber for streaming ingestion progress via SSE.

Handles the asynchronous generator logic to yield ingestion events from
internal queues to HTTP clients using the Server-Sent Events protocol.
Mirrors the audit subscriber pattern but uses ingestion_event_to_sse.
"""

import asyncio
import json
from typing import AsyncIterator

from auditchain.core.logging import get_logger
from auditchain.api.events.ingestion_schemas import ingestion_event_to_sse
from auditchain.api.events.publisher import get_publisher

logger = get_logger(__name__)


async def subscribe_to_ingestion(ingestion_id: str) -> AsyncIterator[str]:
    """Asynchronous generator that produces SSE events for an ingestion run.

    Yields strings formatted according to the SSE protocol.
    Closes when a sentinel (None) is received or an error occurs.
    """
    publisher = get_publisher()
    queue = publisher.get_queue(ingestion_id)

    logger.info("ingestion_subscriber_connected", ingestion_id=ingestion_id)

    # Send initial connection confirmation
    yield f"event: stream_opened\ndata: {json.dumps({'ingestion_id': ingestion_id})}\n\n"

    try:
        while True:
            try:
                # Wait for next event with a heartbeat timeout
                event = await asyncio.wait_for(queue.get(), timeout=30.0)

                if event is None:  # End of stream sentinel
                    yield "event: stream_closed\ndata: {}\n\n"
                    logger.info("ingestion_subscriber_stream_closed", ingestion_id=ingestion_id)
                    break

                yield ingestion_event_to_sse(event)

            except asyncio.TimeoutError:
                # Send heartbeat to keep the connection alive
                yield ": heartbeat\n\n"

    except asyncio.CancelledError:
        logger.info("ingestion_subscriber_disconnected", ingestion_id=ingestion_id)
    except Exception as e:
        logger.error("ingestion_subscriber_error", ingestion_id=ingestion_id, error=str(e))
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    finally:
        logger.info("ingestion_subscriber_completed", ingestion_id=ingestion_id)
