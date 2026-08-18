"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ClientSummary } from "@/lib/types";
import { withClient } from "@/lib/client";
import ClientSelector from "./ClientSelector";
import styles from "./Nav.module.css";

// Ordinals were dropped when Priorities was added. Numbering implied a
// sequence to be walked through, which suited a portfolio piece read once and
// misdescribed a tool returned to weekly: only Outlook is an entry point, and
// the rest are destinations reached in whatever order the question demands.
const ITEMS = [
  { href: "/", label: "Outlook" },
  { href: "/priorities", label: "Priorities" },
  { href: "/planner", label: "Planner" },
  { href: "/evidence", label: "Evidence" },
  { href: "/model", label: "Model" },
];

export default function Nav({
  clients,
  activeClient,
}: {
  clients: ClientSummary[];
  activeClient: string;
}) {
  const pathname = usePathname();
  const client = useSearchParams().get("client") ?? undefined;

  return (
    <header className={styles.nav}>
      <div className={styles.inner}>
        <div className={styles.brand}>
          <Link href={withClient("/", client)} className={styles.wordmark}>
            <span className={styles.wordmarkTitle}>FP&amp;A Decision Intelligence</span>
          </Link>
          <ClientSelector clients={clients} active={activeClient} />
        </div>
        <nav className={styles.links} aria-label="Primary">
          {ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={withClient(item.href, client)}
                className={active ? `${styles.link} ${styles.linkActive}` : styles.link}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
