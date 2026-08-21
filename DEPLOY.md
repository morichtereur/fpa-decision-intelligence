# Deploying

Two hosts: the Next.js frontend on Vercel, the FastAPI backend on Render. Each
side then runs on its platform's default path, with no custom build config on
either.

The API is a long-lived process rather than a serverless function on purpose.
Forecasts, the Monte Carlo and the materiality ranking are cached per client in
memory; functions would recompute them per invocation.

## 1. Backend — Render

1. New → **Blueprint**, point it at this repository. `render.yaml` is picked up
   automatically and creates `fpa-decision-intelligence-api`.
2. Wait for the first deploy, then note the assigned URL
   (`https://fpa-decision-intelligence-api.onrender.com`).
3. Check `GET /api/health` returns `{"status":"ok"}`.

The free tier sleeps after inactivity, so the first request after a quiet
period takes roughly 30 seconds. Worth knowing before a live demo — open the
API health check a minute before you present.

**No LLM key is set, deliberately.** Preset commentary is served from the
committed `data/commentary.json`, and `/api/commentary/live` returns a clear
503. The product is fully usable without it. If you do want live commentary,
set `ANTHROPIC_API_KEY` (or the `BEDROCK_*` pair) in the Render dashboard — and
only on a key with a spend cap, because the endpoint is public.

## 2. Frontend — Vercel

1. New Project → import this repository.
2. **Set the root directory to `web/`.**

   There is deliberately **no `vercel.json` at the repository root**. One used
   to live there from the single-host setup, routing every request to
   `api/index.py`. Even with the root directory set to `web/` and the Next.js
   build succeeding, Vercel applied that routing at runtime: every request —
   the home page, the 404, even `/favicon.ico` — was handed to a Python
   function that cannot import in that environment, and every page returned
   `FUNCTION_INVOCATION_FAILED`. The build looked perfect; only the runtime
   logs showed it. If you ever add a root `vercel.json` back, expect this.

   The framework is declared in `web/vercel.json`, so the preset should read
   **Next.js** on its own. That file holds nothing else: Vercel validates
   `vercel.json` against a strict schema and rejects unknown keys, including
   the `"//"` convention people use for comments. Anything explanatory about
   these files belongs here, not in them. If it says *Other*, the deploy will fail after a
   successful build with `No Output Directory named "public" found` — the
   build produced `.next` while Vercel was looking for a static site.
3. Add one environment variable, for all environments:

   ```
   NEXT_PUBLIC_API_BASE = https://fpa-decision-intelligence-api.onrender.com
   ```

   It is read at build time as well as runtime, so a change needs a redeploy.
4. Deploy, then note the assigned origin.

## 3. Close the CORS loop

The API rejects browser origins it does not know, so the frontend cannot talk
to it until its origin is allowed. In the Render dashboard set:

```
CORS_ORIGINS       = https://<your-vercel-origin>
CORS_ORIGIN_REGEX  = ^https://fpa-decision-intelligence-.*\.vercel\.app$
```

The regex covers Vercel's per-branch preview deployments, which each get their
own subdomain. Redeploy the API for the change to take.

## Live

- Site: https://fpa-decision-intelligence.vercel.app
- API:  https://fpa-decision-intelligence-api.onrender.com

Two settings caused every failure during the first deployment, and neither is
visible from a build log:

- **Root Directory must be `web`.** Left at the repository root, Vercel finds
  `api/index.py`, deploys the Python API as the whole project, and every page
  404s with `{"detail":"Not Found"}` — FastAPI answering for a site that was
  never built.
- **`NEXT_PUBLIC_API_BASE` must exist at build time and must NOT be marked
  Sensitive.** It is compiled into the bundle, so a missing or withheld value
  silently becomes `http://localhost:8000`, and every page reports the engine
  unreachable. Redeploy with the build cache **off** after changing it, or the
  old value survives.

## 4. Check it end to end

- `/` renders the decision brief with a euro figure, not a blank panel
- the model selector switches to Manufacturing and the drivers change
- `/evidence` shows the variance bridge for adidas and an explanation of its
  absence for Manufacturing
- `/planner` recalculates when a slider moves — this is the one that fails
  first if CORS is wrong, because it is the only page that POSTs

If the planner is inert and the console shows a request blocked before a
readable response, it is CORS, not the model.

## Updating the screenshots

`docs/*.png` are captured from a production build, so they never show the dev
overlay:

```bash
npm --prefix web run build
NEXT_PUBLIC_API_BASE=http://localhost:8001 npm --prefix web run start -- --port 3002 &
.venv/bin/python -m uvicorn api.main:app --port 8001 &
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --force-device-scale-factor=2 --hide-scrollbars --window-size=1440,1150 \
  --screenshot="$PWD/docs/outlook.png" http://localhost:3002/
```

Check the captured image before committing it. A screenshot taken against a
stale API server shows stale numbers, and it is not obvious from the file.
