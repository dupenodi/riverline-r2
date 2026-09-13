import type { Metadata, Viewport } from "next";
import { Karla, Newsreader } from "next/font/google";
import "./globals.css";

// Karla carries the interface; Newsreader carries anything Kubera says. The
// split is the point: a question read in a text serif sounds like a person
// asking, and the same sentence in the UI face sounds like a form label.
const karla = Karla({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-karla",
  display: "swap",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  display: "swap",
});

const TITLE = "Kubera";
const DESCRIPTION =
  "Talk through your money and see whether the next thirty days hold.";

export const viewport: Viewport = {
  themeColor: "#F4F7F4",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: TITLE,
    template: `%s · ${TITLE}`,
  },
  description: DESCRIPTION,
  applicationName: TITLE,
  authors: [{ name: TITLE }],
  creator: TITLE,
  keywords: ["voice", "finance", "money", "budget"],
  category: "finance",
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    siteName: TITLE,
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
  appleWebApp: {
    capable: true,
    title: TITLE,
    statusBarStyle: "default",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${karla.variable} ${newsreader.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
