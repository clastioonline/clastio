import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SITE_URL, SOCIAL_IMAGE } from "@/lib/seo";
import { THEME_BOOT_SCRIPT } from "@/lib/theme-boot";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Clastio — AI lesson planning and editable PowerPoints", template: "%s · Clastio" },
  description:
    "Plan lessons and create editable PowerPoints from your own teaching materials and school design. Built for UAE teachers, with British curriculum workflows and teacher review.",
  icons: {
    icon: [{ url: "/brand/favicon.png", type: "image/png", sizes: "192x192" }],
    apple: [{ url: "/brand/favicon.png", sizes: "192x192" }],
  },
  metadataBase: new URL(SITE_URL),
  robots: { index: false, follow: false },
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Clastio" },
  openGraph: {
    type: "website",
    siteName: "Clastio",
    title: "Clastio — AI lesson planning and editable PowerPoints",
    description: "Lesson planning and editable PowerPoints in your own design for UAE teachers.",
    locale: "en_AE",
    images: [SOCIAL_IMAGE],
  },
  twitter: { card: "summary_large_image", title: "Clastio", description: "Lesson planning and editable PowerPoints in your own design.", images: [SOCIAL_IMAGE.url] },
};

export const viewport: Viewport = {
  themeColor: "#1b7446",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-screen antialiased">
        {process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? (
          <ClerkProvider signInUrl="/login" signUpUrl="/signup" signInForceRedirectUrl="/auth/clerk" signUpForceRedirectUrl="/auth/clerk">
            <Providers>{children}</Providers>
          </ClerkProvider>
        ) : <Providers>{children}</Providers>}
      </body>
    </html>
  );
}
