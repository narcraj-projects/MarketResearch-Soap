import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lather Lens",
  description: "Evidence-backed competitor research for handmade soap.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
