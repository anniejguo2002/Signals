# Signal — AI Competitor Intelligence

A polished React + Tailwind dashboard backed by Python FastAPI and the **real TinyFish Search, Fetch, Browser, and Agent APIs**. Enter a company website to research its positioning and discover and research up to three competitors. Compare products, pricing, target customers, and differentiation, with sources attached to individual findings.

There is no mock mode, bundled fictitious report, or alternate AI provider. The sample button launches real research. History contains only runs this installation actually performed.

## Visual report analytics

Every report with at least one researched profile includes an interactive visual overview, including existing saved reports:

- **Source-depth bar chart:** distinct URLs cited across each company's five research dimensions. Repeated citations count once per company; competitor-discovery references are excluded from this chart. These are evidence counts, not product rankings or market share.
- **Coverage donut:** fields with nonempty findings and citations, divided by five dimensions × the number of returned profiles. Missing fields remain visible; failed or still-pending profiles are outside this denominator. Coverage measures citation presence, not independent accuracy.
- **Interactive evidence map:** each cell shows the number of distinct cited pages for a company/dimension. Select a cell to read its exact finding and follow the original sources. Missing data has a separate patterned state.
- **Pricing cards:** expand the comparison to read the original pricing summaries and citations, retaining currencies, billing periods, seat/traffic limits, and custom-pricing details. No inferred price normalization or competitive scores are generated.

Charts update as profiles arrive, support keyboard interactions, and adapt to mobile screens. All calculations happen locally from the existing report; viewing analytics does not launch additional paid TinyFish runs. JSON exports retain the underlying data from which the visuals are calculated.

## Authenticated portals with TinyFish Vault

Signal supports authorized gated content on the **submitted target website** through [TinyFish Vault](https://docs.tinyfish.ai/key-concepts/credentials). Public research remains the default.

1. In TinyFish **Settings → Vault**, connect your password manager and sync its items. Follow the [official setup instructions](https://docs.tinyfish.ai/vault-setup); enter provider secrets only in TinyFish, never in Signal or its `.env`.
2. Make sure the credential includes the target website's domain in your password manager.
3. Enter the HTTPS portal URL in Signal and enable **Use TinyFish Vault for this portal**.
4. Click **Load matching credentials**, select the intended account, and check the authorization statement. Changing the target URL or credential clears authorization.
5. Start research. The backend checks the selection against fresh Vault metadata and passes `use_vault: true` with an explicit `credential_item_ids` list to the target run only. It never enables the API's all-credentials default. Competitor runs explicitly disable Vault and session-profile reuse.

The app returns only matching credential labels, reference IDs, matching domains, and TOTP availability to the selector. It never requests password values. Credential references stay in the request/job memory and are not stored in SQLite reports or exports. Only `access_mode: vault` is saved. Target findings are not passed to competitor sessions. Prompts restrict portal research to company/product information, prohibit account changes and credential disclosure, and require login outcomes/limitations in the report notes. These are agent instructions, not a guarantee against every website behavior.

Vault does not bypass paywalls, account permissions, CAPTCHAs, or subscriptions. TOTP can work when configured in the Vault item; hardware keys and push MFA are unsupported, and some OAuth/SSO flows may fail. This integration uses fresh sessions and does not create or reuse Browser Context Profiles. Failed login must be reported as a limitation, not claimed as successful authentication.

Authenticated reports can contain gated information and are labeled accordingly. Reports and exports are saved locally; review them before sharing. Signal is a single-user loopback demo with no app-level authentication—do not expose this Vault-enabled server publicly without adding user authentication, authorization, and credential ownership checks.

Additional endpoint: `GET /api/vault/items?url=https%3A%2F%2Fportal.example.com` returns matching display metadata. To launch via API, add `use_vault: true`, a nonempty `credential_item_ids` array, and `authorize_portal: true` to the research request. HTTP targets, empty/unmatched selections, and missing authorization are rejected before a paid run is created.

## Quick start

Requirements: **Python 3.11+**, **Node.js 20.19+ or 22.12+**, and **pnpm 11+** (or npm). A TinyFish API key with sufficient wallet funds is required for live research.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Only do this if you haven't already created .env:
cp .env.example .env
```

Add your key in `.env`:

```dotenv
TINYFISH_API_KEY=your_key_here
DATABASE_PATH=data/research.sqlite3
RESEARCH_TIMEOUT_SECONDS=480
```

Get a key from [TinyFish](https://agent.tinyfish.ai/api-keys). `.env` and all generated research data are gitignored. Keys are read **only by FastAPI** and sent to TinyFish in `X-API-Key`. Never put the key in a `VITE_` variable. An exported environment variable takes precedence over `.env`. Saving a key to `.env` does not require a server restart.

Install and start the frontend:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

In another terminal, from the project root:

```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to FastAPI. API docs are at **http://127.0.0.1:8000/docs**. If using npm instead, use `npm install` and `npm run dev` in `frontend`; the committed pnpm lockfile is the reproducible installation path.

## Single-server demo / production build

```bash
cd frontend
pnpm build
cd ..
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. FastAPI serves the compiled React application and API from the same origin. Build **before** starting the backend, or restart after the first build. Use one worker: background jobs and concurrency limits are managed by that process. No Node server is required after building.

## Reliable hackathon walkthrough

1. Start the app and configure the key.
2. Click **Research Plausible**. This submits `https://plausible.io` with a one-competitor limit, using exactly the same live pipeline as a normal URL submission. Public SaaS product/pricing pages make this a focused demonstration; sites and availability can still change.
3. Show live research progress. TinyFish first researches the company and discovers an evidence-backed alternative, then researches that alternative independently.
4. Open **Comparison**, **Sources**, and **Research log**. Explain that missing details stay marked “Not found”; no default prices or competitor data are filled in.
5. Click **Export report** to download JSON containing the findings, sources, timestamps, limitations, and TinyFish run IDs.
6. Before presenting, finish one live run. During the presentation, either rerun it live or select the completed report from **Research history** / **Open Plausible Analytics**. Saved results are explicitly labeled **Saved live research** and dated. This is a real prior run, not a live replay or a mock.

The first verified demo in this workspace researched **Plausible Analytics and Matomo** through two actual TinyFish runs in approximately three minutes. Its local artifact is `data/live-demo.json`; it is intentionally not committed. A clean checkout has no preloaded research. Selecting up to three competitors may take longer and can involve up to four paid TinyFish runs. Fewer than three may be returned if fewer can be substantiated.

The final full live demo also completed successfully: **Plausible Analytics, Matomo, Simple Analytics, and Cloudflare Web Analytics**. Its genuine output is `data/full-live-demo-corrected.json`, and the report is available in Research history. Product-scoped prompts keep competitors within the relevant category rather than comparing unrelated parent-company products.

## Implementation and API contract

Official documentation inspected before implementation:

- [Agent API reference](https://docs.tinyfish.ai/agent-api/reference)
- [Streaming endpoint](https://docs.tinyfish.ai/api-reference/automation/run-browser-automation-with-sse-streaming)
- [Structured output and account requirements](https://docs.tinyfish.ai/key-concepts/structured-output)
- [Run lifecycle](https://docs.tinyfish.ai/key-concepts/runs)
- [Error codes](https://docs.tinyfish.ai/error-codes)

The implementation uses one provider, a public evidence preparation stage, and two Agent research phases:

1. FastAPI validates the submitted public URL, resolves it to reject private addresses, and creates a SQLite report.
2. For public targets, Search, Fetch, and Browser run concurrently to collect discovery leads, fresh text, and a rendered preview (see the four-tool pipeline below). Then `POST https://agent.tinyfish.ai/v1/automation/run-sse` with `{url, goal, agent_config: {max_duration_seconds}}` researches the target and finds up to three supported candidates. Authentication uses the server-side `X-API-Key` header.
3. `STARTED` / `PROGRESS` events and run IDs are stored in SQLite. The frontend polls our report endpoint every 1.5 seconds; refreshes and navigating away do not cancel a job.
4. The `COMPLETE` event must have `status: COMPLETED` and valid research data. The parser supports documented `result` and nested `result.result`, JSON strings/code fences, and legacy `resultJson`.
5. Competitor runs use the same endpoint, with at most two concurrent browser sessions. Duplicate domains and brands, the target company, and candidates without discovery evidence are excluded.
6. Pydantic validates every profile. Text without source URLs becomes unavailable. Entirely empty profiles fail validation. Individual competitor failures become a partial report without discarding valid findings.
7. If the upstream stream disconnects after a run ID is received, the backend polls `GET /v1/runs/{id}` instead of launching a duplicate paid run. Timeouts attempt `POST /v1/runs/{id}/cancel`.

The code does not send `output_schema`, strict mode, or `max_steps`: those can require extra TinyFish account entitlements. JSON is requested in the goal and validated locally. Invalid data results in an explicit error, never a made-up fallback.

### Local endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Server and key-presence status; never returns the key |
| POST | `/api/research` | Start `{ "url": "https://plausible.io", "competitor_limit": 1 }`; returns 202 and report ID |
| GET | `/api/research` | Latest 100 reports |
| GET | `/api/research/{id}` | Progress, findings, errors, sources, and TinyFish runs |
| GET | `/api/research/{id}/export` | Download the report as JSON |

### Project layout

```text
backend/
  main.py          FastAPI routes, configuration, job lifecycle, static hosting
  models.py        URL validation and source-backed research contracts
  tinyfish.py      Real HTTP/SSE adapter, polling recovery and cancellation
  toolkit.py       Real Search/Fetch clients and remote Browser capture
  research.py      Prompts, discovery and competitor orchestration
  store.py         SQLite report persistence
  tests/           Isolated contract, safety and error-path tests
frontend/
  src/App.tsx      React interface and progress polling
  src/ReportAnalytics.tsx  Evidence charts, coverage, drill-down, pricing cards
  src/ResearchTools.tsx  Four-tool status, source inputs, and browser preview
  src/main.tsx     React entry point
  src/styles.css   Tailwind entry point and responsive design system
scripts/
  live_smoke.py    Real end-to-end API test and genuine report export
data/             Local reports / SQLite database; gitignored
```

## Testing

```bash
source .venv/bin/activate
python -m pytest backend/tests -q
cd frontend && pnpm build
```

Tests use isolated synthetic transport fixtures **only inside the test suite** to exercise errors and recovery deterministically. They are not exposed to the application, sample workflow, or final demo.

With the app running and a valid TinyFish key, run the **real integration smoke test**:

```bash
python scripts/live_smoke.py
# Full landscape:
python scripts/live_smoke.py --competitors 3 --output data/full-live-demo.json
# Validate a run already submitted in the UI without creating another paid run:
python scripts/live_smoke.py --report-id YOUR_REPORT_ID
```

The smoke test requires a completed report with the target plus at least one competitor, actual TinyFish run IDs, source URLs for every displayed finding, and an exact export round-trip. It saves the real response in `data/live-demo.json` by default. It does not accept partial results as a successful live test.

Verified in this workspace: **45 passing backend tests**, TypeScript checking and production build, genuine two-company and four-company live API runs, desktop and 390px mobile browser checks, progress, history, source/log tabs, invalid-URL errors, JSON export, and FastAPI serving the compiled frontend. The API key was checked to be absent from the compiled browser assets. One third-party test-client deprecation warning does not affect test results.

## Operational limits and troubleshooting

- **401 / 403:** check the key or account permissions. **402:** check the TinyFish wallet. **429:** wait before retrying. Errors are shown in the interface; provider error bodies and secrets are not forwarded.
- **Blocked or unavailable pages:** individual fields may be absent, or a competitor may fail. Try fewer competitors or a different site. For a target portal, explicitly select Vault access as described above; the app does not bypass access controls or paywalls.
- **Evidence quality:** all research is extracted by TinyFish from public websites, and claims must have cited source URLs. Citation presence is validated; semantic accuracy and page availability are not independently guaranteed. Marketing statements, especially claimed differentiation, should be checked against the original pages. The interface says “source-backed,” not independently fact-checked.
- **Pricing:** summaries retain available currency, billing period, volume/seat limits, and annual-billing qualifications. They are not normalized into misleading price rankings.
- **Upstream timeout:** default 480 seconds per browser run, configurable between 60 and 1800 seconds. The app does not automatically retry paid submissions. If a connection dies before a run ID is returned, inspect your TinyFish dashboard before retrying.
- **Server restart:** unfinished local reports are marked failed; previously saved findings remain. Graceful shutdown attempts to cancel active provider runs. After a hard crash, check the linked TinyFish run before submitting again.
- **Local hackathon scope:** the app has no authentication or user isolation and allows one active report at a time. Keep it bound to loopback. Before public deployment, add authentication, per-user authorization, rate limits, spend controls, durable workers, and stricter network egress controls. SQLite and in-process jobs suit a local demo, not a multi-worker deployment.
- **Resetting local research:** stop the server and move `data/research.sqlite3` somewhere safe to start fresh. This is optional; keeping successful live reports makes demos resilient.


## Four-tool research pipeline

New public reports use all four official APIs with the same server-side key:

1. **[Search](https://docs.tinyfish.ai/search-api/reference)** — `GET https://api.search.tinyfish.ai`, querying the public hostname for competitor leads. Retains up to eight linked results.
2. **[Fetch](https://docs.tinyfish.ai/fetch-api/reference)** — `POST https://api.fetch.tinyfish.ai`, collecting the target page as Markdown with `ttl: 0` for a fresh retrieval. Stores at most 10,000 characters.
3. **[Browser](https://docs.tinyfish.ai/browser-api/reference)** — creates an isolated public session, connects with Playwright over CDP, and captures a 1280×800 screenshot. Deletes the remote session in `finally` with bounded retries; the session also has a 120-second inactivity timeout. No local Chromium installation is required. CDP URLs and API keys never reach the frontend.
4. **Agent** — receives bounded, untrusted Search/Fetch context, visits and verifies sources, then researches the selected competitors in separate sessions. Search snippets alone are not accepted as verified findings.

The first three run concurrently before Agent discovery. The report shows actual completion/failure states, discovery links, fetched excerpts, and the rendered preview. Tool failure does not fabricate results or prevent Agent from attempting independent research. Older saved reports show “not recorded” for newly added tools. Analytics count cited profile findings, not search leads or screenshots.

Vault reports skip all three public preparatory tools to keep portal URLs and private content confined to the authorized Agent run. The direct Browser API is a separate public session, not the Agent's authenticated browser.

Screenshot endpoint: `GET /api/research/{id}/preview`. Files are saved under gitignored `data/previews/`; JSON exports link to that local endpoint rather than embedding image bytes. Preserve this folder alongside the SQLite database when moving saved reports.

Verify the complete public workflow against real APIs (consumes TinyFish credits):

```bash
python scripts/live_smoke.py --competitors 1 --require-tools --output data/four-tool-demo.json
```

To recheck an existing report without starting another paid run, add `--report-id <id>`.

## Interactive strategy playground

Every report with at least one researched company includes a dark, neon-accented strategy lab. Use a report with three competitors to compare four companies on the positioning map.

- Select a company bubble or legend entry to edit its **assumed price and perceived-value indices**. Hover and keyboard focus enlarge bubbles and reveal coordinates; touch selection uses the same editing controls.
- Explore your pricing change (−50% to +50%), an assumed product-launch value gain (0–40 points), competitors’ assumed price cuts (0–40%), and buyer price sensitivity (0–100%). The map, attractiveness scores, and rank update immediately.
- Dashed points show starting positions. Colored bubbles show the scenario; equal sizes deliberately do not imply market share.
- Save up to three scenarios and restore them for comparison. Saves are in-memory for the current report view/session; reload or switching reports resets them. They do not alter verified research or its JSON export.
- Consult the selected company's cited pricing and differentiation while choosing assumptions.

**These are hypothetical scenarios, not verified forecasts.** Initial map coordinates are illustrative presets, not values extracted from company websites. The app never claims these are measured positioning, market share, revenue, or demand. The transparent model is:

`score = price_weight × (100 − price_index) + (1 − price_weight) × perceived_value`

Pricing changes scale the original price index. A launch adds assumed value points. Indices are clamped to 0–100. Rankings include only researched companies, with equal scores sharing rank. The model omits adoption, time, costs, demand elasticity, brand awareness differences, and probabilities. No extra API call is made when moving sliders.

Pure model checks (Node 22.18+):

```bash
node --experimental-strip-types scripts/test_strategy.mjs
```

These cover unchanged baselines, tied rankings, price sensitivity, buyer weighting, competitor reactions, bounds, and input immutability. UI checks also cover saved-scenario restore, reset, company selection, and a 390px mobile layout.

The genuine four-tool demo is saved locally as `data/four-tool-demo.json`, report `396b402f-e9e0-4f38-bb6a-2258f3170c6f` (Plausible and Matomo). Search, Fetch, Browser PNG retrieval, Agent profiles, and JSON export all passed live verification. The earlier four-company report `b63d86b6-29e3-4708-9226-d29d37fa240b` is useful for the strategy playground; its newly added tool cards correctly say “not recorded.”

### Feature-based SaaS launch scenarios

The launch planner replaces the generic value-gain slider with proposed feature additions or upgrades: funnels (for analytics reports), client reporting, API/data integrations, SSO/access controls, setup/migration, and alerts. Feature cards show related keyword matches from cited product and differentiation summaries; these are review leads, not verified parity or proof that a feature is absent.

Choose a buyer segment, edit estimated effort and potential value for each feature, and set capacity, adoption, and readiness. Launch lift is the sum of selected feature value × segment-fit assumption, multiplied by adoption, readiness, and `min(1, capacity / estimated effort)`, capped at 40 points. The generic preset estimates and segment-fit multipliers are illustrative planning assumptions, not research-derived benchmarks. Scope over capacity reduces modeled benefit. Saved scenarios now preserve the full launch plan. Pricing and competitor-response controls still work independently. Existing competitor analysis remains above the simulator.

## Weekly email competitor briefs

Completed public reports offer an email signup and a **clearly labeled fictional sample email** for display. Samples are never stored as research, used in scoring, or emailed as live findings. Coverage KPIs are companies refreshed, distinct cited pages, and sourced fields; briefs summarize pricing, products, and differentiation with original URLs. Changed extraction wording is labeled “summary differs — verify source,” not a verified product change.

Configure the new blank fields in `.env` to enable delivery:

```dotenv
SMTP_HOST=smtp.your-provider.example
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=Signal <verified-sender@your-domain.example>
PUBLIC_BASE_URL=https://your-deployed-app.example
```

Use a provider-authorized sender and STARTTLS SMTP. The public HTTPS URL must reach this running app so recipients can confirm and unsubscribe. No credentials are placed in the frontend. Without configuration, signups persist as pending and the UI explicitly states that delivery is not active. Once configured, the worker sends a confirmation email; the recipient must click the confirmation page's button. The first brief is due seven days later, then every seven days after delivery.

SQLite persists subscriptions, opt-in state, next due time, last delivered report, and bounded failure retries. A single-process background worker checks every 60 seconds, respects the foreground research gate, refreshes the original companies through real TinyFish Agent calls, and compares with the last delivered report. It never substitutes old findings for failed fresh research. Public reports only; Vault content cannot be subscribed. Emails include research gaps, source URLs, the full report, and an unsubscribe link. Links show a confirmation form before changing state to avoid mail-scanner activation/unsubscription. Weekly work uses TinyFish credits.

Run exactly one backend worker continuously. Due jobs run after restart, rather than sending missed historical weeks. Failures retry hourly up to three attempts; inspect `subscriptions.last_error` and `attempts` in the SQLite database to diagnose paused deliveries. SMTP delivery is not exactly-once: a process crash after SMTP acceptance but before saving state can cause a duplicate. This local hackathon app needs authentication, per-user authorization, abuse controls, and an external durable job queue before public multi-tenant deployment. Local report URLs are not usable by remote email recipients.

API: `GET /api/weekly/status`, `POST /api/weekly/subscribe` with `{email, report_id, consent:true}`, and token-based confirmation/unsubscribe pages. The UI never exposes the subscriber list. Tests isolate email transport; no real email was sent during implementation. End-to-end SMTP delivery requires your configured provider and verified sender.
