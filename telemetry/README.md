# H3 Studio aggregate counter

H3 Studio includes an optional, privacy-minimal aggregate counter for successful generated images. The counter accepts only `{ "count": 1..100, "schema": 1 }`, adds that number to one global Durable Object total, and exposes `/v1/count` plus `/badge.svg`.

It does **not** accept or store prompts, images, references, seeds, hardware details, file paths, installation identifiers, or other generation metadata. Both the client implementation (`h3studio/telemetry.py`) and the Cloudflare Worker implementation (`telemetry/worker.js`) are public so the complete path can be inspected.

The counter Worker explicitly disables persistent Workers observability logs and Workers Logpush in `wrangler.toml`. No Tail Worker is configured. Cloudflare still necessarily sees network-level metadata while routing a direct request, and an authorized Worker owner can use live debugging tools such as `wrangler tail`; disabling persisted logs does not change that fact.

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

`H3STUDIO_TELEMETRY=0` can still be set before starting ComfyUI for launch scripts, containers and other advanced setups. An environment override that disables telemetry takes precedence even if the per-install opt-out file is removed.

The client batches counts and sends them asynchronously so telemetry does not block image generation. Network failures are ignored.
