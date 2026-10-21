/** Parse chunked UTF-8 SSE, including the final unterminated frame. */
export async function readOperationResult<T, E = { type: string; stage: string; status: string; message?: string | null }>(
  response: Response, onProgress?: (event: E) => void,
): Promise<T> {
  if (!response.body) throw new Error("没有收到数据，请重试。");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  function frame(text: string): { data: T } | undefined {
    const data = text.split("\n").filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart()).join("\n");
    if (!data) return;
    const event = JSON.parse(data);
    if (event.type === "progress") onProgress?.(event as E);
    if (event.type === "error") throw new Error(event.message || "请求处理失败，请重试。");
    if (event.type === "result") return { data: event.data as T };
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      // Preserve split CRLF sequences until both bytes arrive.
      buffer = buffer.replace(/\r\n/g, "\n");
      let split: number;
      while ((split = buffer.indexOf("\n\n")) >= 0) {
        const result = frame(buffer.slice(0, split));
        buffer = buffer.slice(split + 2);
        if (result) return result.data;
      }
      if (done) {
        const result = frame(buffer);
        if (result) return result.data;
        throw new Error("连接已中断，未收到完成结果，请重试。");
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
