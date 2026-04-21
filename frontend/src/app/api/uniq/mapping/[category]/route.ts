import { uniq, ApiError, type MappingUpdate } from "@/lib/api";

export async function GET(
  _req: Request,
  ctx: RouteContext<"/api/uniq/mapping/[category]">,
) {
  const { category } = await ctx.params;
  try {
    return Response.json(await uniq.getMapping(category));
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json({ detail: "FastAPI unreachable" }, { status: 502 });
  }
}

export async function PATCH(
  req: Request,
  ctx: RouteContext<"/api/uniq/mapping/[category]">,
) {
  const { category } = await ctx.params;
  let update: MappingUpdate;
  try {
    update = (await req.json()) as MappingUpdate;
  } catch {
    return Response.json({ detail: "Invalid JSON body" }, { status: 400 });
  }
  try {
    return Response.json(await uniq.patchMapping(category, update));
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json({ detail: "FastAPI unreachable" }, { status: 502 });
  }
}
