import type { Metadata } from "next";
import { Archivo, Source_Serif_4, IBM_Plex_Mono } from "next/font/google";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import { api } from "@/lib/api";
import type { ClientSummary } from "@/lib/types";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "FP&A Decision Intelligence Accelerator",
  description:
    "A configurable FP&A decision-support accelerator: driver-based forecasting, scenario planning, "
    + "and quantified financial exposures ranked into management priorities.",
};

/** The nav needs the list of planning models, and the API is the only place
 *  that knows them. Failing soft matters here: if the API is unreachable the
 *  shell should still render so the page below can report the real error,
 *  rather than the whole app 500ing on its own chrome. */
async function loadClients(): Promise<{ clients: ClientSummary[]; active: string }> {
  try {
    const { clients, default: fallback } = await api.clients();
    return { clients, active: fallback };
  } catch {
    return { clients: [], active: "" };
  }
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const { clients, active } = await loadClients();

  return (
    <html lang="en" className={`${archivo.variable} ${sourceSerif.variable} ${plexMono.variable}`}>
      <body>
        <Suspense>
          <Nav clients={clients} activeClient={active} />
        </Suspense>
        <main>{children}</main>
      </body>
    </html>
  );
}
