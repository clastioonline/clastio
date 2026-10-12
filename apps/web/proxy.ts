import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";
import { renderSystemPageHtml, systemPageForSlug } from "@/lib/system-pages";
import { THEME_BOOT_SCRIPT } from "@/lib/theme-boot";

const clerk = clerkMiddleware({ authorizedParties: [process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"] });
export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const path = request.nextUrl.pathname;
  const slug = path.startsWith("/") && !path.slice(1).includes("/") ? path.slice(1) : "";
  const page = systemPageForSlug(slug);
  if (page && ["GET", "HEAD"].includes(request.method)) {
    return new NextResponse(request.method === "HEAD" ? null : renderSystemPageHtml(page, THEME_BOOT_SCRIPT), {
      status: page.status,
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow", "X-Clastio-System-Page": page.slug,
        ...(page.status === 401 ? { "WWW-Authenticate": 'Bearer realm="Clastio"' } : {}) },
    });
  }
  return process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? clerk(request, event) : NextResponse.next();
}
export const config = { matcher: ["/((?!_next|.*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|mp4|vtt)).*)"] };
