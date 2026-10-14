import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "JHunt: Thailand Tech Market Intelligence",
    short_name: "JHunt",
    description:
      "Portfolio architecture specifications derived from live Thailand tech demand signals.",
    start_url: "/",
    display: "standalone",
    background_color: "#08080a",
    theme_color: "#06b6d4",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
