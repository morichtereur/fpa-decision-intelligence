import { redirect } from "next/navigation";
import { clientFrom, withClient, type SearchParams } from "@/lib/client";

/** The screen was renamed when the credibility material moved onto it: it is
 *  no longer only forecast and risk, it is everything a reader needs to decide
 *  whether to believe the numbers. The old path still resolves so existing
 *  links keep working. */
export default async function ForecastRiskRedirect({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  redirect(withClient("/evidence", clientFrom(await searchParams)));
}
