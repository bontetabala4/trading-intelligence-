import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ATIP — Recherche et paper trading",
  description: "Aide à la décision, sans exécution réelle.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
