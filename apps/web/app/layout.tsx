import type { Metadata, Viewport } from "next";
import "./globals.css";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Clastio — lessons and slides in your own design", template: "%s · Clastio" },
  description:
    "Your personal AI teaching assistant: lessons, slides in your own design, worksheets, quizzes and daily plans on WhatsApp.",
  icons: { icon: "/brand/clastio-original.png" },
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  openGraph: {
    type: "website",
    siteName: "Clastio",
    title: "Clastio — lessons and slides in your own design",
    description: "Lessons, slides in your own design, worksheets, quizzes and daily plans for teachers.",
  },
  twitter: { card: "summary", title: "Clastio", description: "Lessons and slides in your own design." },
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
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
