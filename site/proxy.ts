import { NextRequest, NextResponse } from "next/server";

/**
 * Soft gate for /dashboard/* — if there is no session cookie, redirect
 * to the login page. The real authoritative check still happens
 * server-side via /api/auth/me; this avoids flashing the dashboard
 * shell to a signed-out visitor.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!pathname.startsWith("/dashboard")) return NextResponse.next();
  if (pathname.startsWith("/dashboard/login")) return NextResponse.next();

  const session = request.cookies.get("cp_session");
  if (!session) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
