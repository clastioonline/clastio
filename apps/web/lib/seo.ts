import type { Metadata } from "next";
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://clastio.online").replace(/\/+$/, "");
export function pageMetadata(title: string, description: string, path: string): Metadata {
  return { title, description, alternates: { canonical: `${SITE_URL}${path}` },
    openGraph: { title, description, url: `${SITE_URL}${path}`, siteName: "Clastio", type: "website", locale: "en_AE", images: [{ url: "/brand/clastio-original.png", alt: "Clastio teaching assistant" }] },
    twitter: { card: "summary", title, description, images: ["/brand/clastio-original.png"] },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 } },
  };
}
export function jsonLd(value: unknown) { return JSON.stringify(value).replace(/</g, "\\u003c"); }
