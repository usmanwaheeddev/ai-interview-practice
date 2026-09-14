import { apiRequest } from "../../lib/api";
import type { MediaKind } from "../../lib/types";

export class ChunkedMediaUploader {
  private chunkIndex = 0;
  private pending: Promise<void>[] = [];
  private successful: number[] = [];
  constructor(private interviewId: string, private kind: MediaKind) {}
  uploadChunk(blob: Blob): void {
    const index = this.chunkIndex++;
    const task = (async () => {
      const {upload_url} = await apiRequest<{upload_url:string}>(`/mock-interviews/${this.interviewId}/media`, {
        method:"POST", body:{kind:this.kind, chunk_index:index, content_type:blob.type || `${this.kind}/webm`}
      });
      const result = await fetch(upload_url, {method:"PUT", body:blob, headers:{"Content-Type":blob.type || `${this.kind}/webm`}});
      if (!result.ok) throw new Error("Recording upload failed");
      this.successful.push(index);
    })();
    task.catch(err => console.error("Recording chunk failed", err));
    this.pending.push(task);
  }
  async complete(): Promise<void> {
    await Promise.allSettled(this.pending);
    await apiRequest(`/mock-interviews/${this.interviewId}/media/complete`, {method:"POST", body:{chunk_indices:this.successful}});
  }
}
