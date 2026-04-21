import { uniq, ApiError } from "@/lib/api";

export async function GET(
  _req: Request,
  ctx: RouteContext<"/api/uniq/patients/[id]">,
) {
  const { id } = await ctx.params;
  const numeric = Number(id);
  if (!Number.isFinite(numeric)) {
    return Response.json({ detail: "user_id must be numeric" }, { status: 400 });
  }
  try {
    return Response.json(await uniq.getPatient(numeric));
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json({ detail: "FastAPI unreachable" }, { status: 502 });
  }
}
