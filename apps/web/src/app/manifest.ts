import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Kubera",
    short_name: "Kubera",
    description:
      "I help you talk through your money and see what the month can hold.",
    start_url: "/",
    display: "standalone",
    background_color: "#F7F7F9",
    theme_color: "#F7F7F9",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
