/**
 * BFF for clinical annotations on a single patient.
 *
 * Living-substrate beat: clinicians don't just sign the schema; they
 * contribute clinical context back into the record. GET returns every
 * annotation for the patient (chronological); POST appends a new note
 * and the backend persists atomically through the JSON store.
 *
 * Author / role / timestamp / id are filled server-side from the
 * authenticated session (today: a single demo clinician). The client
 * payload only carries the note, an optional event_id pin, and an
 * optional category — keeping the write surface narrow on purpose.
 */

import type {
  ClinicalAnnotation,
  ClinicalAnnotationCreate,
} from "@/lib/api";

const FASTAPI_BASE = process.env.UNIQ_API_BASE ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await ctx.params;
  const upstream = await fetch(
    `${FASTAPI_BASE}/v1/patients/${encodeURIComponent(id)}/annotations`,
    { cache: "no-store" },
  ).catch(() => null);

  if (!upstream) {
    return Response.json([] satisfies ClinicalAnnotation[], { status: 200 });
  }
  if (!upstream.ok) {
    const detail = await upstream.text();
    return new Response(detail, { status: upstream.status });
  }
  return Response.json(await upstream.json());
}

export async function POST(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await ctx.params;
  const payload = (await req.json()) as ClinicalAnnotationCreate;

  const upstream = await fetch(
    `${FASTAPI_BASE}/v1/patients/${encodeURIComponent(id)}/annotations`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    },
  ).catch(() => null);

  if (!upstream) {
    return Response.json(
      { detail: "FastAPI unreachable" },
      { status: 502 },
    );
  }

  const body = await upstream.json().catch(() => ({}));
  return Response.json(body, { status: upstream.status });
}
