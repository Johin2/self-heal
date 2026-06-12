import { NextRequest } from "next/server";
import { proxy } from "@/lib/control-plane";

export async function GET(request: NextRequest) {
  return proxy(request, "/v1/keys");
}

export async function POST(request: NextRequest) {
  return proxy(request, "/v1/keys");
}
