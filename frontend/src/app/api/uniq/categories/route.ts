import { uniq, ApiError } from "@/lib/api";

export async function GET() {
  try {
    return Response.json(await uniq.categories());
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json({ detail: "FastAPI unreachable" }, { status: 502 });
  }
}
