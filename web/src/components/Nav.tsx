"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

// Ordinals were dropped when Priorities was added. Numbering implied a
// sequence to be walked through, which suited a portfolio piece read once and
// misdescribed a tool returned to weekly: only Outlook is an entry point, and
// the rest are destinations reached in whatever order the question demands.
const ITEMS = [
  { href: "/", label: "Outlook" },
  { href: "/priorities", label: "Priorities" },
  { href: "/planner", label: "Planner" },
  { href: "/forecast-risk", label: "Forecast & Risk" },
  { href: "/model", label: "Model" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className={styles.nav}>
      <div className={styles.inner}>
        <Link href="/" className={styles.wordmark}>
          <span className={styles.wordmarkTitle}>FP&amp;A Decision Model</span>
          <span className={styles.wordmarkSub}>adidas AG · FY2025</span>
        </Link>
        <nav className={styles.links} aria-label="Primary">
          {ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
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
