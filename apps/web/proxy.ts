import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";

const clerk = clerkMiddleware({ authorizedParties: [process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"] });
export default function proxy(request: NextRequest, event: NextFetchEvent) {
  return process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? clerk(request, event) : NextResponse.next();
}
export const config = { matcher: ["/((?!_next|.*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|mp4|vtt)).*)"] };
