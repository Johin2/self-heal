import type { Metadata } from "next";
import { Geist, Geist_Mono, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "self-heal: the reliability layer for AI agents",
  description:
    "Make your LLM agents repair themselves at runtime. Open source Python library. Works with Claude, OpenAI, Gemini, and 100+ providers.",
  openGraph: {
    title: "self-heal: the reliability layer for AI agents",
    description:
      "Make your LLM agents repair themselves at runtime. Open source, MIT licensed.",
    url: "https://github.com/Johin2/self-heal",
    siteName: "self-heal",
  },
  metadataBase: new URL("https://github.com/Johin2/self-heal"),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-black text-neutral-100">
        {children}
      </body>
    </html>
  );
}
