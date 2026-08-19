# H3 Studio aggregate counter

H3 Studio's optional generated-image counter uses hosted GoatCounter instead of a project-operated telemetry endpoint.

The client sends only a counter hit for the fixed path `/generated` with GoatCounter's `ns=1` flag. It does **not** send prompts, images, references, seeds, hardware details, file paths, installation identifiers, workflow data, or other generation metadata. No GoatCounter API key is shipped in H3 Studio.

The client keeps a small local aggregate so image generation is never blocked. When that aggregate flushes, it is expanded in one background sender into minimal `/count` requests, serialized at 0.40 seconds apart so it stays below GoatCounter's public `count` rate limit. The requests use the fixed `H3-Studio/2 Counter` User-Agent and contain only `p=/generated&ns=1`.

`ns=1` explicitly disables GoatCounter session tracking for these hits. The H3 Studio GoatCounter site also has the optional collection dimensions disabled that are not needed for this counter: sessions, individual pageviews, location, browser/system, referrers, language, and screen size. The only statistic H3 Studio needs is the aggregate count for `/generated`.

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

Each generated image becomes one GoatCounter hit for `/generated` with session tracking disabled. The README badge reads the public aggregate counter through GoatCounter; no API token is embedded in the repository or client.

### One-time migration from the old counter

The repository includes `tools/migrate_counter_to_goatcounter.py` only for the one-time historical migration from the old Cloudflare counter. It reads the API token from `GOATCOUNTER_API_TOKEN` and never writes that token to the repository.

Dry-run:

```bash
python tools/migrate_counter_to_goatcounter.py --code <code>
```

Apply:

```bash
GOATCOUNTER_API_TOKEN=<token> python tools/migrate_counter_to_goatcounter.py --code <code> --apply
```

PowerShell:

```powershell
$env:GOATCOUNTER_API_TOKEN = "<token>"
python .\tools\migrate_counter_to_goatcounter.py --code <code> --apply
Remove-Item Env:GOATCOUNTER_API_TOKEN
```

The migration API batches up to 500 historical hits per request and sets `no_sessions: true`. It must not be run again against the already-seeded H3 Studio site because that would duplicate the historical total.

The legacy Cloudflare Worker may remain deployed temporarily so older already-installed H3 Studio releases do not break, but current H3 Studio builds report directly to GoatCounter and do not use that Worker as their telemetry ingress.
