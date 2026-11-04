import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Estimador TRI ENEM",
  description: "Consulta de questões do ENEM preparada para evolução com TRI.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
