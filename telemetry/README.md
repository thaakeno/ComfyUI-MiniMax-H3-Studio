# H3 Studio aggregate counter

H3 Studio is migrating its optional generated-image counter from a project-operated Cloudflare Worker to hosted GoatCounter.

The client sends only a counter hit for the fixed path `/generated` with GoatCounter's `ns=1` flag. It does **not** send prompts, images, references, seeds, hardware details, file paths, installation identifiers, workflow data, or other generation metadata. No GoatCounter API key is shipped in H3 Studio.

The client keeps a small local aggregate so image generation is never blocked. When that aggregate flushes, it is expanded in one background sender into anonymous `/count` requests, serialized at 0.40 seconds apart so it stays below GoatCounter's public `count` rate limit. The requests use a fixed H3 Studio User-Agent and contain only `p=/generated&ns=1`.

`ns=1` explicitly disables GoatCounter session tracking for these hits. For the H3 Studio site, the owner should also disable every optional collection dimension that is not needed for this counter: sessions, individual pageviews, location, browser/system, referrers, language, and screen size. The only required statistic is the aggregate count for `/generated`.

The hosted GoatCounter service is operated independently from H3 Studio. H3 Studio therefore does not operate the server receiving client telemetry connections.

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

During migration/testing, `H3STUDIO_TELEMETRY_ENDPOINT=https://<code>.goatcounter.com/count` can override the built-in endpoint.

### One-time migration from the old counter

Create a GoatCounter API key in the GoatCounter account, keep it local, then dry-run:

```bash
python tools/migrate_counter_to_goatcounter.py --code <code>
```

The script fetches the legacy Cloudflare lifetime total and shows how many GoatCounter API requests will be needed. It does not modify GoatCounter unless `--apply` is passed.

To apply the migration without ever putting the API key in the repository:

```bash
GOATCOUNTER_API_TOKEN=<token> python tools/migrate_counter_to_goatcounter.py --code <code> --apply
```

PowerShell:

```powershell
$env:GOATCOUNTER_API_TOKEN = "<token>"
python .\tools\migrate_counter_to_goatcounter.py --code <code> --apply
Remove-Item Env:GOATCOUNTER_API_TOKEN
```

The migration API batches up to 500 historical hits per request and sets `no_sessions: true`. Run it only against the new empty GoatCounter site so the lifetime total is not duplicated.

### Cutover checklist

1. Create the hosted GoatCounter site and disable all optional collection dimensions listed above.
2. Enable GoatCounter's public visitor counter if the README should display the total directly from GoatCounter.
3. Dry-run and then apply the one-time legacy count migration.
4. Bake the public `https://<code>.goatcounter.com/count` URL into `h3studio/telemetry.py`.
5. Replace the README's old Cloudflare badge/counter URL with GoatCounter's public counter.
6. Remove the legacy Cloudflare Worker files and decommission the deployed Worker so old H3 Studio versions can no longer send telemetry to project-operated infrastructure.
