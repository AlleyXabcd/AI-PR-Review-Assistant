import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI PR Review 助手",
  description: "指定 GitHub PR，自动获取变更并由 AI 辅助分析。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
