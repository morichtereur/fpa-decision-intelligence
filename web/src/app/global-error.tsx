"use client";

/**
 * Last resort: a failure in the root layout itself, which the route-level
 * boundary cannot catch because it lives inside that layout. Deliberately
 * dependency-free and self-styled — whatever broke may be the very thing the
 * normal styling relies on.
 */
export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          padding: "3rem 1.5rem",
          background: "#e9eae4",
          color: "#121a17",
          fontFamily: "Georgia, 'Times New Roman', serif",
        }}
      >
        <main style={{ maxWidth: "42rem", margin: "0 auto" }}>
          <p
            style={{
              fontSize: "0.75rem",
              letterSpacing: "0.09em",
              textTransform: "uppercase",
              color: "#59635e",
              margin: 0,
            }}
          >
            Model unavailable
          </p>
          <h1 style={{ fontSize: "1.75rem", lineHeight: 1.1, margin: "0.75rem 0 1rem" }}>
            The decision engine did not answer.
          </h1>
          <p style={{ color: "#59635e", lineHeight: 1.6 }}>
            Every figure here is computed on request, so there is nothing honest to show while
            the engine is unreachable. It sleeps after inactivity and takes about a minute to
            wake — reloading usually resolves it.
          </p>
          {(error.message || error.digest) && (
            <p
              style={{
                fontFamily: "ui-monospace, Menlo, monospace",
                fontSize: "0.75rem",
                color: "#59635e",
                borderTop: "1px solid #c6cac0",
                paddingTop: "0.75rem",
                overflowWrap: "anywhere",
              }}
            >
              {error.message || error.digest}
            </p>
          )}
        </main>
      </body>
    </html>
  );
}
