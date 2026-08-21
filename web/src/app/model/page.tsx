import { api } from "@/lib/api";
import { clientFrom, type SearchParams } from "@/lib/client";
import DriverTree from "@/components/DriverTree";
import AssumptionRegister from "@/components/AssumptionRegister";
import MetricMap from "@/components/MetricMap";
import ModelReadiness from "@/components/ModelReadiness";
import styles from "./model.module.css";

export const dynamic = "force-dynamic";

export default async function ModelPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const client = clientFrom(await searchParams);
  const [assumptions, summary, drivers, mappings, readiness] = await Promise.all([
    api.assumptions(client),
    api.client(client),
    api.drivers(client),
    api.mappings(client),
    api.readiness(client),
  ]);

  return (
    <div className={styles.page}>
      <div className={`label ${styles.eyebrow}`}>Model · {summary.short_label} · {summary.industry}</div>
      <h1 className={styles.heading}>How the forecast is actually built</h1>
      <p className={styles.intro}>
        No step here requires reading Python to understand. The calculation chain is fixed by
        the model; the drivers hanging off it come from {summary.name}&rsquo;s own configuration,
        which is where a client&rsquo;s economics live. The model is authoritative — this page is
        a window into it, not a separate description of it.
      </p>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>What this model can answer</h2>
        <p className={styles.sectionIntro}>
          Before the numbers are worth arguing about, the model has to be able to say who owns
          each driver, how far it could plausibly move, and what level would be worth a
          conversation. Most planning models cannot, and that is a finding rather than an
          obstacle to one.
        </p>
        <ModelReadiness readiness={readiness} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Calculation chain</h2>
        <p className={styles.sectionIntro}>
          The chain is fixed by the model. The drivers to its right are
          {" "}{summary.short_label}&rsquo;s own, and change with the planning model.
        </p>
        <DriverTree drivers={drivers} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Where the data comes from</h2>
        <p className={styles.sectionIntro}>
          The contract this model expects from any source system, and how {summary.short_label}
          &rsquo;s figures resolve to it. No connector is implemented — what is real here is the
          shape the mapping would take.
        </p>
        <MetricMap mappings={mappings} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Assumption register</h2>
        <p className={styles.sectionIntro}>Click a row for its source and guidance context.</p>
        <AssumptionRegister rows={assumptions} />
      </section>

    </div>
  );
}
