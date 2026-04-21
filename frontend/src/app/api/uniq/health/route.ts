import { uniq, ApiError } from "@/lib/api";

export async function GET() {
  try {
    const data = await uniq.health();
    return Response.json(data);
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json(
      { detail: "FastAPI unreachable", message: String(error) },
      { status: 502 }
    );
  }
}
