import type { Metadata, Viewport } from "next";
import "./globals.css";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "AI Teacher Assistant", template: "%s · AI Teacher Assistant" },
  description:
    "Your personal AI teaching assistant: lessons, slides in your own design, worksheets, quizzes and daily plans on WhatsApp.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#4f46e5",
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
