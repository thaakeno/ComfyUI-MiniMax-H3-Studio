# H3 Studio aggregate counter backend

This Cloudflare Worker accepts only `{ "count": 1..100, "schema": 1 }`, atomically adds the count in one Durable Object, and exposes `/v1/count` plus `/badge.svg`. It has no request logging code, database rows, installation identifiers, or fields for prompts and generation metadata.

Deploy from this directory with a Cloudflare account:

```bash
npx wrangler login
npx wrangler deploy
curl https://h3-studio-counter.<your-subdomain>.workers.dev/v1/count
```

Set `H3STUDIO_TELEMETRY_ENDPOINT` if the deployed hostname differs from the project default. Configure Cloudflare rate limiting for `POST /v1/report`; the public endpoint deliberately contains no reusable client secret because shipping one in a custom node would not authenticate installations.
