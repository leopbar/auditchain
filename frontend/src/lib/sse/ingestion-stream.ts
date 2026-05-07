import type { IngestionEvent } from "@/types/ingestion";
import { API_BASE_URL } from "@/lib/api/client";

export type IngestionStreamHandlers = {
  onEvent?: (event: IngestionEvent) => void;
  onOpen?: () => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
};

export class IngestionStreamClient {
  private eventSource: EventSource | null = null;
  private ingestionId: string;
  private handlers: IngestionStreamHandlers;
  private closed = false;

  constructor(ingestionId: string, handlers: IngestionStreamHandlers = {}) {
    this.ingestionId = ingestionId;
    this.handlers = handlers;
  }

  connect(): void {
    if (this.eventSource) {
      console.warn("IngestionStreamClient already connected");
      return;
    }

    const url = `${API_BASE_URL}/api/companies/add/${this.ingestionId}/stream`;
    this.eventSource = new EventSource(url, { withCredentials: true });

    this.eventSource.onopen = () => {
      this.handlers.onOpen?.();
    };

    this.eventSource.onerror = (error) => {
      if (this.closed) return;

      this.handlers.onError?.(error);

      if (this.eventSource?.readyState === EventSource.CLOSED) {
        this.handlers.onClose?.();
      }
    };

    // Listeners for specific ingestion event types
    const eventTypes = [
      "ingestion_started",
      "stage_started",
      "stage_progress",
      "stage_completed",
      "ingestion_completed",
      "ingestion_failed",
      "stream_closed",
    ];

    for (const eventType of eventTypes) {
      this.eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as IngestionEvent;
          this.handlers.onEvent?.(data);

          if (eventType === "stream_closed") {
            this.disconnect();
            this.handlers.onClose?.();
          }
        } catch (err) {
          console.error("Failed to parse ingestion SSE event", err);
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
