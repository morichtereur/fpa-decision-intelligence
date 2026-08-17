import styles from "./MetricDisplay.module.css";

export default function MetricDisplay({
  label,
  value,
  caption,
}: {
  label: string;
  value: string;
  caption?: string;
}) {
  return (
    <div className={styles.metric}>
      <div className={`label ${styles.label}`}>{label}</div>
      <div className={`mono ${styles.value}`}>{value}</div>
      {caption && <div className={styles.caption}>{caption}</div>}
    </div>
  );
}
