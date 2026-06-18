import { NextRequest } from "next/server";
import { proxy } from "@/lib/control-plane";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxy(request, `/v1/keys/${id}`);
}
