import { uniq, ApiError } from "@/lib/api";

export async function POST(req: Request) {
  let body: { message?: string; session_id?: string };
  try {
    body = (await req.json()) as { message?: string; session_id?: string };
  } catch {
    return Response.json({ detail: "Invalid JSON body" }, { status: 400 });
  }
  if (!body.message || typeof body.message !== "string") {
    return Response.json({ detail: "message is required" }, { status: 400 });
  }
  try {
    return Response.json(await uniq.chat(body.message, body.session_id));
  } catch (error) {
    if (error instanceof ApiError) {
      return Response.json(error.detail, { status: error.status });
    }
    return Response.json({ detail: "FastAPI unreachable" }, { status: 502 });
  }
}
