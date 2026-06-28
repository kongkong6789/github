import type { Metadata } from "next";
import "./globals.css";
import React from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";

export const metadata: Metadata = {
  title: "A2A 电商经营大脑",
  description: "面向电商经营、资料整理和老板汇报的本地工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
    >
      <body className="antialiased">
        <NuqsAdapter>{children}</NuqsAdapter>
      </body>
    </html>
  );
}
