import { uniq, ApiError } from "@/lib/api";

export async function GET() {
  try {
    return Response.json(await uniq.substrateManifest());
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json(
      { detail: "FastAPI unreachable", message: String(error) },
      { status: 502 },
    );
  }
}
