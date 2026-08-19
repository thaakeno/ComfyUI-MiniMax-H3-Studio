# H3 Studio generated-image counter

H3 Studio's current generated-image counter uses hosted GoatCounter instead of a project-operated telemetry ingress.

The current client sends only a counter hit for the fixed path `/generated` with GoatCounter's `ns=1` flag. It does **not** send prompts, images, references, seeds, hardware details, file paths, installation identifiers, workflow data, or other generation metadata. No GoatCounter API key is shipped in H3 Studio.

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

The current client endpoint is:

```text
https://h3-studio.goatcounter.com/count
```

Each generated image becomes one GoatCounter hit for `/generated` with session tracking disabled.

### README badge

The README uses the existing Cloudflare Worker URL only as a **display proxy** for the badge. `/badge.svg` fetches the current GoatCounter aggregate with a per-request cache-busting query, formats it with an English comma thousands separator, and returns `Cache-Control: no-cache, no-store` so GitHub's image proxy revalidates instead of holding the old number.

The badge proxy never receives reports from current H3 Studio builds. Current telemetry goes directly to GoatCounter.

The Worker still keeps the old `/v1/report` and `/v1/count` routes temporarily for backward compatibility with already-installed H3 Studio versions. Those old versions still have the Cloudflare endpoint baked into their local code; keeping the route alive lets their remaining generations be measured and delta-imported during the cutover. Once old-version coverage is no longer needed, the legacy report route and Durable Object can be retired.

### One-time migration from the old counter

The repository includes `tools/migrate_counter_to_goatcounter.py` for the historical migration and later legacy-version delta imports. It reads the API token from `GOATCOUNTER_API_TOKEN` and never writes that token to the repository.

The migration API batches up to 500 historical hits per request and sets `no_sessions: true`. Never re-import the full historical baseline after cutover; only import the additional legacy Cloudflare delta since the saved cutover checkpoint.
