import type { AuditEvent } from "@/types/audit";
import { API_BASE_URL } from "@/lib/api/client";

export type AuditStreamHandlers = {
  onEvent?: (event: AuditEvent) => void;
  onOpen?: () => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
};

export class AuditStreamClient {
  private eventSource: EventSource | null = null;
  private runId: string;
  private handlers: AuditStreamHandlers;
  private closed = false;
  
  constructor(runId: string, handlers: AuditStreamHandlers = {}) {
    this.runId = runId;
    this.handlers = handlers;
  }
  
  connect(): void {
    if (this.eventSource) {
      console.warn("AuditStreamClient already connected");
      return;
    }
    
    const url = `${API_BASE_URL}/api/audits/${this.runId}/stream`;
    this.eventSource = new EventSource(url);
    
    this.eventSource.onopen = () => {
      this.handlers.onOpen?.();
    };
    
    this.eventSource.onerror = (error) => {
      // If manually closed, ignore errors
      if (this.closed) return;
      
      this.handlers.onError?.(error);
      
      // EventSource tries to reconnect automatically; check if it's dead
      if (this.eventSource?.readyState === EventSource.CLOSED) {
        this.handlers.onClose?.();
      }
    };
    
    // Listeners for specific audit event types
    const eventTypes = [
      "audit_started",
      "phase_started",
      "tool_called",
      "tool_completed",
      "phase_completed",
      "phase_failed",
      "audit_completed",
      "audit_failed",
      "stream_closed",
    ];
    
    for (const eventType of eventTypes) {
      this.eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as AuditEvent;
          this.handlers.onEvent?.(data);
          
          // Note: Termination events are handled via stream_closed signal
          if (eventType === "stream_closed") {
            this.disconnect();
            this.handlers.onClose?.();
          }
        } catch (err) {
          console.error("Failed to parse SSE event", err);
        }
      });
    }
  }
  
  disconnect(): void {
    this.closed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
  
  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN;
  }
}
