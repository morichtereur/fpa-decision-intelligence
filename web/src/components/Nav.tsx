"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const ITEMS = [
  { href: "/", label: "01 Outlook" },
  { href: "/planner", label: "02 Scenario Planner" },
  { href: "/forecast-risk", label: "03 Forecast & Risk" },
  { href: "/model", label: "04 Model & Assumptions" },
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
