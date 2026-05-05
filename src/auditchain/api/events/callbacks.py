"""LangChain callback handler for audit events.

Intercepts tool execution within the multi-agent graph and publishes real-time 
progress events to the AuditChain event stream (SSE).
"""

import time
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from auditchain.core.logging import get_logger
from auditchain.api.events.schemas import ToolCalledEvent, ToolCompletedEvent
from auditchain.api.events.publisher import get_publisher

class AuditChainCallbackHandler(AsyncCallbackHandler):
    """Callback that intercepts tool calls from LangChain and publishes SSE events.
    
    Each audit run has its own instance of this handler to ensure proper 
    state tracking (phase, run_id, timing).
    """
    
    def __init__(self, run_id: str, audit_started_at: float):
        self.run_id = run_id
        self.audit_started_at = audit_started_at  # Timestamp of when the overall audit started
        self.current_phase: str = "unknown"  # Updated by the audit_runner node by node
        self.publisher = get_publisher()
        self.logger = get_logger(__name__)
        self._tool_start_times: Dict[str, float] = {}  # Map of tool run_ids to their start timestamps
    
    def set_current_phase(self, phase: str):
        """Updates the internal phase tracker. Should be called by nodes before agent invocation."""
        self.current_phase = phase
    
    def _elapsed(self) -> float:
        """Calculates elapsed seconds since the start of the audit."""
        return time.time() - self.audit_started_at
    
    def _truncate_input(self, input_str: str) -> Dict[str, str]:
        """Creates a summarized input dictionary, truncating long strings for SSE efficiency."""
        result = {}
        if isinstance(input_str, str) and len(input_str) > 200:
            result["preview"] = input_str[:200] + "..."
        elif isinstance(input_str, str):
            result["preview"] = input_str
        else:
            result["preview"] = str(input_str)[:200]
        return result
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Triggered when a tool starts execution."""
        tool_name = serialized.get("name", "unknown_tool")
        
        # Internal submit tools are skipped to reduce noise in the frontend
        if tool_name.startswith("submit_"):
            return
        
        # Track start time for duration calculation in on_tool_end
        self._tool_start_times[str(run_id)] = time.time()
        
        # Publish event for the UI
        event = ToolCalledEvent(
            run_id=self.run_id,
            elapsed_seconds=self._elapsed(),
            phase=self.current_phase,
            tool_name=tool_name,
            tool_input=self._truncate_input(input_str),
        )
        await self.publisher.publish(event)
        self.logger.info("callback_tool_start", phase=self.current_phase, tool=tool_name)
    
    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Triggered when a tool finishes successfully."""
        tool_run_id_str = str(run_id)
        start_time = self._tool_start_times.pop(tool_run_id_str, None)
        
        if start_time is None:
            # Likely a submit_* tool that we skipped in on_tool_start
            return
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Retrieve tool name from kwargs if possible
        tool_name = kwargs.get("name", "unknown_tool")
        
        event = ToolCompletedEvent(
            run_id=self.run_id,
            elapsed_seconds=self._elapsed(),
            phase=self.current_phase,
            tool_name=tool_name,
            duration_ms=duration_ms,
            success=True,
        )
        await self.publisher.publish(event)
        self.logger.info("callback_tool_end", phase=self.current_phase, tool=tool_name, ms=duration_ms)
    
    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Triggered when a tool execution fails."""
        tool_run_id_str = str(run_id)
        start_time = self._tool_start_times.pop(tool_run_id_str, None)
        duration_ms = int((time.time() - start_time) * 1000) if start_time else 0
        
        tool_name = kwargs.get("name", "unknown_tool")
        
        event = ToolCompletedEvent(
            run_id=self.run_id,
            elapsed_seconds=self._elapsed(),
            phase=self.current_phase,
            tool_name=tool_name,
            duration_ms=duration_ms,
            success=False,
        )
        await self.publisher.publish(event)
        self.logger.warning("callback_tool_error", phase=self.current_phase, tool=tool_name, error=str(error))

    # --- No-op handlers to prevent NotImplementedError in some environments ---
    
    async def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_chain_start(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_chain_end(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_chain_error(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_llm_end(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    async def on_llm_error(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass
