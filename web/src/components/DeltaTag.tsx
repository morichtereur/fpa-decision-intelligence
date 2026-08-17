import type { DeltaDirection } from "@/lib/format";
import styles from "./DeltaTag.module.css";

export default function DeltaTag({
  text,
  direction,
}: {
  text: string;
  direction: DeltaDirection;
}) {
  return <span className={`mono ${styles.tag} ${styles[direction]}`}>{text}</span>;
}
