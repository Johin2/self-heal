import { NextRequest } from "next/server";
import { proxy } from "@/lib/control-plane";

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return proxy(request, `/v1/keys/${params.id}`);
}
