import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const base = process.env.TAMPAK_API_URL ?? "http://127.0.0.1:8100";
  const target = new URL(
    `/api/v1/${path.map(encodeURIComponent).join("/")}`,
    base,
  );
  target.search = request.nextUrl.search;
  const headers = new Headers();
  for (const key of [
    "cookie",
    "content-type",
    "x-csrf-token",
    "origin",
    "last-event-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  let body: Uint8Array | undefined;
  if (!["GET", "HEAD"].includes(request.method)) {
    const reader = request.body?.getReader();
    const pieces: Uint8Array[] = [];
    let size = 0;
    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 11 * 1024 * 1024) {
        await reader.cancel();
        return Response.json(
          {
            error: {
              message: "Upload a file up to 10 MB.",
              code: "UPLOAD_SIZE",
            },
          },
          { status: 413 },
        );
      }
      pieces.push(value);
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const piece of pieces) {
      body.set(piece, offset);
      offset += piece.byteLength;
    }
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      cache: "no-store",
      signal: request.signal,
      redirect: "manual",
    });
    const outgoing = new Headers(response.headers);
    outgoing.delete("content-encoding");
    outgoing.delete("content-length");
    outgoing.set("Cache-Control", "no-store, no-transform");
    outgoing.set("X-Accel-Buffering", "no");
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    return Response.json(
      {
        error: {
          code: "API_UNAVAILABLE",
          message:
            "The local API is unavailable. Check that the backend is running.",
        },
      },
      { status: 503 },
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as PUT,
  proxy as DELETE,
};
