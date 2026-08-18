/**
 * Reading the active planning model off the URL.
 *
 * The client lives in a query parameter rather than a cookie or a context
 * provider. Three reasons, in order of weight: a link to a specific client's
 * priorities is shareable and survives a paste into an email, which is how
 * this product would actually be used; server components can read it without
 * any client-side hydration; and it cannot go stale the way a cookie can when
 * two tabs are open on two different models.
 */

export type SearchParams = Record<string, string | string[] | undefined>;

export function clientFrom(params: SearchParams | undefined): string | undefined {
  const raw = params?.client;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value && value.length > 0 ? value : undefined;
}

/** Preserve the active model when linking between pages. */
export function withClient(href: string, client: string | undefined): string {
  if (!client) return href;
  return `${href}${href.includes("?") ? "&" : "?"}client=${encodeURIComponent(client)}`;
}
