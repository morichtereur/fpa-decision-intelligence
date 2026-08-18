"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import type { ClientSummary } from "@/lib/types";
import styles from "./ClientSelector.module.css";

/**
 * Selection of the active planning model — not a theme switcher.
 *
 * It sits in the wordmark slot because that is where a reader already looks
 * to orient, and because the thing it replaced was a hardcoded label saying
 * which company this was. Rendered as a labelled select rather than a
 * segmented control or a row of pills: those read as view options, and this
 * changes the drivers, the currency, the thresholds and the ranking.
 */
export default function ClientSelector({
  clients,
  active,
}: {
  clients: ClientSummary[];
  active: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  if (clients.length < 2) return null;

  function select(id: string) {
    const next = new URLSearchParams(params.toString());
    next.set("client", id);
    startTransition(() => router.push(`${pathname}?${next.toString()}`));
  }

  // The URL is the source of truth; `active` is only the fallback the API
  // reports as its default.
  const selected = params.get("client") ?? active;
  const current = clients.find((c) => c.id === selected) ?? clients[0];

  return (
    <div className={styles.wrap} data-pending={pending ? "" : undefined}>
      <label className={styles.label} htmlFor="active-model">
        Planning model
      </label>
      <div className={styles.control}>
        <select
          id="active-model"
          className={styles.select}
          value={current.id}
          onChange={(event) => select(event.target.value)}
        >
          {clients.map((client) => (
            <option key={client.id} value={client.id}>
              {client.short_label} · {client.data_basis}
            </option>
          ))}
        </select>
        <span className={styles.caret} aria-hidden="true">
          ▾
        </span>
      </div>
    </div>
  );
}
