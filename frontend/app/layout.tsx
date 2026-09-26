import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "FORGE — the AI engineer that finds bugs, fixes them, and shows its work",
  description:
    "FORGE is an automated software engineer. You describe a bug in plain words, and FORGE reads your code, finds the real cause, writes and tests the fix, checks for security problems, and hands you a release-ready result with evidence.",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={display.variable}>{children}</body>
    </html>
  );
}