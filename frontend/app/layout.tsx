import type { Metadata } from "next";
import "./globals.css";
import Analytics from "@/components/shell/Analytics";

export const metadata: Metadata = {
  title: "A 360° view of the business, in SQL — Aito",
  description:
    "Root causes and the lever that moves each, computed by an Aito predictive database " +
    "and asked entirely in SQL over the Postgres wire protocol. No model is trained and " +
    "nothing is precomputed — every number on the page is one statement you can read and edit.",
  openGraph: {
    title: "A 360° view of the business, in SQL",
    description:
      "Six questions, twenty-four SQL statements, no training step — one of the six cards " +
      "deliberately fails.",
    images: ["/teaser.png"],
  },
  icons: {
    icon: "/aito-favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Analytics />
        {children}
      </body>
    </html>
  );
}
