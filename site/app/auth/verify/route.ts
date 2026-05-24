import { NextRequest, NextResponse } from "next/server";
import { proxy } from "@/lib/control-plane";

/**
 * Server-side magic-link verify. The user clicks the link in their email,
 * we POST the token to the backend, and on success we redirect them into
 * the dashboard while passing through the Set-Cookie that the backend
 * issued.
 */
export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");
  if (!token) {
    return NextResponse.redirect(new URL("/dashboard/login?error=missing", request.url));
  }

  // Wrap the request to give the proxy helper a synthetic POST body.
  const body = JSON.stringify({ token });
  const synthetic = new NextRequest(request.nextUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });

  const upstream = await proxy(synthetic, "/v1/auth/verify");

  if (upstream.status !== 200) {
    return NextResponse.redirect(new URL("/dashboard/login?error=invalid", request.url));
  }

  const redirect = NextResponse.redirect(new URL("/dashboard", request.url));
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    redirect.headers.set("set-cookie", setCookie);
  }
  return redirect;
}
