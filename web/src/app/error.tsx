"use client";

import ApiUnavailable from "@/components/ApiUnavailable";

/**
 * Route-level error boundary.
 *
 * Every page is server-rendered from the model, so the realistic failure is
 * "the engine did not answer" — an API asleep on its free tier, or a frontend
 * built against the wrong host. Without this the reader gets the platform's
 * own crash page, which names neither.
 */
export default function Error({ error }: { error: Error & { digest?: string } }) {
  return <ApiUnavailable detail={error.message || error.digest} />;
}
