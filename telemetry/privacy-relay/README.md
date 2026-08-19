# H3 Studio privacy relay

This is an optional mixing relay for the aggregate image counter. Its purpose is to keep the H3 Studio counter backend from receiving the original client's network address.

For the trust separation to be real, this relay must be operated by an independent account/operator from the H3 Studio counter backend. Deploying both sides under the same operator does not remove the operator's ability to observe the first hop in real time.

The relay accepts exactly `{ "count": 1..100, "schema": 1 }`. It rejects extra JSON fields, rebuilds a new internal request without copying client headers, cookies, user agent, URL or IP metadata, mixes reports into one global integer, then forwards aggregate chunks at randomized 5-15 minute intervals. It stores only the pending integer needed for the next flush.

Both Workers Logs persistence and Workers Logpush are explicitly disabled in `wrangler.toml`. No Tail Worker is configured.

## Deploy under the independent relay account

```bash
cd telemetry/privacy-relay
npx wrangler login
npx wrangler secret put UPSTREAM_TOKEN
npx wrangler deploy
```

Use a long random `UPSTREAM_TOKEN`. Give the same value to the counter operator and configure it there as `RELAY_TOKEN`:

```bash
cd telemetry
npx wrangler secret put RELAY_TOKEN
npx wrangler deploy
```

Once the independent relay URL exists, verify the relay itself first:

```bash
curl -fsS https://<relay-host>/healthz
curl -i -X POST https://<relay-host>/v1/report -H "Content-Type: application/json" --data '{"count":1,"schema":1}'
```

The POST should return HTTP `202`. Because reports are deliberately mixed and delayed, the counter backend will increase within roughly 5-15 minutes rather than immediately. For a local H3 Studio test before changing the built-in default, set `H3STUDIO_TELEMETRY_ENDPOINT=https://<relay-host>/v1/report`, generate an image, then wait for the mixing window and check `/v1/count`.

After the relay has been verified, the built-in `DEFAULT_ENDPOINT` can be changed to the relay URL in a normal release. Do not enable `RELAY_TOKEN` on the counter before clients have been moved to the relay, otherwise older direct clients will receive HTTP 403 and their counts will be dropped.
