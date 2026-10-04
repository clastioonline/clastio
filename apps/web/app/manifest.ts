import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Clastio — your teaching assistant",
    short_name: "Clastio",
    description: "Plan lessons, build teaching slides and receive updates when your work is ready.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    background_color: "#f2f3f0",
    theme_color: "#1b7446",
    icons: [
      { src: "/brand/favicon.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/brand/app-icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
    shortcuts: [
      { name: "Activity", url: "/activity" },
      { name: "Settings", url: "/settings" },
    ],
  };
}
