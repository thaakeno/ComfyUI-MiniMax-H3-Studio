# H3 Studio generated-image counter

H3 Studio's current generated-image counter uses hosted GoatCounter directly instead of a project-operated telemetry ingress.

The entire telemetry implementation now lives inside this top-level `telemetry/` directory. The main H3 Studio runtime only contains an optional loader at the generation call site. If this directory is missing, that loader resolves to a no-op and H3 Studio continues normally without telemetry.

If you want telemetry removed entirely from your local install, delete the whole `telemetry/` directory and restart ComfyUI.

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force .\telemetry
```

Linux/macOS:

```bash
rm -rf telemetry
```

The runtime telemetry file is `telemetry/telemetry.py`. It contains the GoatCounter endpoint, request code, background reporter and persistent opt-out handling.

The current client sends only a counter hit for the fixed path `/generated` with GoatCounter's `ns=1` flag. It does **not** send prompts, images, references, seeds, hardware details, file paths, installation identifiers, workflow data, or other generation metadata. No GoatCounter API key is shipped in H3 Studio.

Each successful output count is queued immediately on a daemon background thread; there is no 10-image/60-second local batching delay anymore. If one H3 execution produces multiple successful images, that integer count is expanded into one GoatCounter `/count` hit per image. All sender threads share one lock and keep 0.40 seconds between requests so independent generations cannot burst above GoatCounter's public count rate limit. Generation itself never waits for the network.

The requests use the fixed `H3-Studio/2 Counter` User-Agent and contain only `p=/generated&ns=1`.

`ns=1` explicitly disables GoatCounter session tracking for these hits. The H3 Studio GoatCounter site also has optional collection dimensions disabled that are not needed for this counter: sessions, individual pageviews, location, browser/system, referrers, language, and screen size. The only statistic H3 Studio needs is the aggregate generated-image count.

The hosted GoatCounter service is operated independently from H3 Studio. GoatCounter necessarily receives the network connection, including the source IP needed for routing and rate limiting, but H3 Studio does not send an IP address as a telemetry field and the H3 Studio operator does not control GoatCounter's ingress or server logs.

Telemetry is enabled by default and can be disabled at any time.

### Persistent opt-out

From the H3 Studio directory, run:

```bash
python telemetry/telemetry.py disable
```

This works on Windows, Linux and macOS. The command creates the per-install opt-out and prints `H3 telemetry: DISABLED` only after the telemetry check confirms that reporting is disabled.

Check the current effective state with:

```bash
python telemetry/telemetry.py status
```

Remove the per-install opt-out with:

```bash
python telemetry/telemetry.py enable
```

If the whole `telemetry/` directory has been deleted, telemetry is already fully removed and no disable command is needed.

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

The README badge reads the public GoatCounter aggregate directly. There is no Cloudflare badge proxy in the current telemetry path. GoatCounter formats the public count using the configured comma thousands separator.

GoatCounter documents that its public visitor-counter responses may be cached for up to four hours, so the README display can lag behind the ingest even though generation reports themselves are sent immediately.

### Legacy Cloudflare cutover

Older already-installed H3 Studio versions may still have the previous Cloudflare `/v1/report` endpoint baked into their local code. The old deployed Worker can remain online temporarily for those installs even though its source/config are no longer part of the current branch.

`telemetry/migrate_legacy_counter.py` is a maintainer-only migration helper for the historical Cloudflare count and later legacy-version delta imports. It is not imported or executed by H3 Studio during normal use. It reads the API token from `GOATCOUNTER_API_TOKEN` and never writes that token to the repository.

The migration API batches up to 500 historical hits per request and sets `no_sessions: true`. Never re-import the full historical baseline after cutover; only import the additional legacy Cloudflare delta since the saved cutover checkpoint.

For later syncs, pass the last saved legacy total with `--delta-from`. The script fetches the current legacy total, imports only the increase, and prints the next checkpoint after a successful apply:

```powershell
python .\telemetry\migrate_legacy_counter.py --code h3-studio --delta-from 9058 --apply
```

Replace `9058` with the last `Next legacy checkpoint` value on subsequent syncs.
