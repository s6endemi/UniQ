/**
 * Snapshot CSV export proxy for substrate resources.
 *
 * Positioning: snapshot export, not "download your database". Wellsters
 * operational system stays the source of record; UniQ continuously
 * materialises the clinical truth layer beside it. This endpoint exists
 * as the trust / interop / audit signal — proof you can take a frozen
 * substrate snapshot out for BI, compliance, or partner handoff.
 *
 * Streams the response from FastAPI through the Next.js BFF so the
 * FastAPI base URL stays out of the client bundle. Content-Type and
 * Content-Disposition headers are forwarded as-is so the browser
 * triggers a real download with the canonical "uniq-{name}-snapshot.csv"
 * filename set by the backend.
 */

const FASTAPI_BASE = process.env.UNIQ_API_BASE ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ name: string }> },
): Promise<Response> {
  const { name } = await ctx.params;
  const upstream = await fetch(
    `${FASTAPI_BASE}/v1/substrate/resources/${encodeURIComponent(name)}/export.csv`,
    { cache: "no-store" },
  ).catch(() => null);

  if (!upstream) {
    return Response.json(
      { detail: "FastAPI unreachable" },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "text/plain" },
    });
  }

  // Forward the file body + relevant headers. Streaming via the body
  // pass-through keeps memory flat for the 100 MB survey_unified.csv
  // case; headers preserve the canonical download filename.
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const contentDisposition = upstream.headers.get("content-disposition");
  const contentLength = upstream.headers.get("content-length");
  if (contentType) headers.set("content-type", contentType);
  if (contentDisposition) headers.set("content-disposition", contentDisposition);
  if (contentLength) headers.set("content-length", contentLength);

  return new Response(upstream.body, {
    status: 200,
    headers,
  });
}
