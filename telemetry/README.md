# H3 Studio generated-image counter

H3 Studio's optional generated-image counter uses hosted GoatCounter instead of a project-operated telemetry ingress.

The client sends only a counter hit for the fixed path `/generated` with GoatCounter's `ns=1` flag. It does **not** send prompts, images, references, seeds, hardware details, file paths, installation identifiers, workflow data, or other generation metadata. No GoatCounter API key is shipped in H3 Studio.

Each successful output count is queued immediately on a daemon background thread; there is no 10-image/60-second local batching delay anymore. If one H3 execution produces multiple successful images, that integer count is expanded into one GoatCounter `/count` hit per image. All sender threads share one lock and keep 0.40 seconds between requests so independent generations cannot burst above GoatCounter's public count rate limit. Generation itself never waits for the network.

The requests use the fixed `H3-Studio/2 Counter` User-Agent and contain only `p=/generated&ns=1`.

`ns=1` explicitly disables GoatCounter session tracking for these hits. The H3 Studio GoatCounter site also has optional collection dimensions disabled that are not needed for this counter: sessions, individual pageviews, location, browser/system, referrers, language, and screen size. The only statistic H3 Studio needs is the aggregate generated-image count.

The hosted GoatCounter service is operated independently from H3 Studio. GoatCounter necessarily receives the network connection, including the source IP needed for routing and rate limiting, but H3 Studio does not send an IP address as a telemetry field and the H3 Studio operator does not control GoatCounter's ingress or server logs.

Telemetry is enabled by default and can be disabled at any time.

### Persistent opt-out

From the H3 Studio directory, run:

```bash
python -m h3studio.telemetry disable
```

This works on Windows, Linux and macOS. The command creates the per-install opt-out and prints `H3 telemetry: DISABLED` only after H3 Studio's own telemetry check confirms that reporting is disabled.

Check the current effective state with:

```bash
python -m h3studio.telemetry status
```

Remove the per-install opt-out with:

```bash
python -m h3studio.telemetry enable
```

### Temporary environment override

`H3STUDIO_TELEMETRY=0` can be set before starting ComfyUI for launch scripts, containers and other advanced setups. An environment override that disables telemetry takes precedence even if the per-install opt-out file is removed.

`H3STUDIO_TELEMETRY_ENDPOINT=https://<code>.goatcounter.com/count` can override the built-in endpoint for testing or custom deployments.

### Counter endpoint

The built-in endpoint is:

```text
https://h3-studio.goatcounter.com/count
```

Each generated image becomes one GoatCounter hit for `/generated` with session tracking disabled.

## Read-only README badge proxy

`telemetry/worker.js` is no longer a telemetry receiver. It is a **read-only badge/count proxy** for the README.

H3 Studio clients never send generation reports to this Worker. It accepts only `GET`/`HEAD` and exposes:

```text
/badge.svg
/v1/count
/count.json
/healthz
```

For a near-live badge, the Worker can use GoatCounter's authenticated statistics API and cache the aggregate for only 10 seconds. GoatCounter itself persists incoming pageviews in the background, so this is near-real-time rather than literally instantaneous. The public GoatCounter visitor-counter endpoint remains a fallback if the read-only API token is missing or temporarily unavailable.

The Worker secret must be a **separate GoatCounter API token with only `Read statistics` permission** for the `h3-studio` site. Do not reuse or ship a pageview-recording token. GoatCounter defines `Read statistics` separately from `Record pageviews`, so the badge Worker does not need permission to write any analytics data.

From the repository after pulling this branch:

```powershell
cd telemetry
npx wrangler secret put GOATCOUNTER_API_TOKEN
npx wrangler deploy
```

`wrangler secret put` prompts for the token value so it is not written to shell history or the repository.

The Worker retains the existing `h3-studio-counter` name so the README can keep the same clean `/badge.svg` URL and visual style. The legacy Durable Object counter is retired with the `v2` deletion migration; its old stored number is no longer needed because the historical total has already been migrated to GoatCounter.

The badge response asks downstream proxies not to cache it, but GitHub renders external README images through its own image proxy, so GitHub can still add some refresh delay outside H3 Studio's control.

### One-time migration from the old counter

The repository includes `tools/migrate_counter_to_goatcounter.py` only for the completed one-time historical migration from the old Cloudflare counter. It reads the API token from `GOATCOUNTER_API_TOKEN` and never writes that token to the repository.

The migration API batches up to 500 historical hits per request and sets `no_sessions: true`. It must **not** be run again against the already-seeded H3 Studio site because that would duplicate the historical total.
