import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BriefDocument AI",
  description: "Giao diện chat đơn giản để tóm tắt văn bản bằng Ollama"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
