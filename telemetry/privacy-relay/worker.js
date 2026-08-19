const MIN_FLUSH_MS = 5 * 60 * 1000;
const MAX_FLUSH_MS = 15 * 60 * 1000;
const RETRY_MIN_MS = 60 * 1000;
const RETRY_MAX_MS = 5 * 60 * 1000;
const MAX_REPORT = 100;
const MAX_BODY_BYTES = 128;

function randomDelay(min, max) {
  const span = max - min + 1;
  const value = crypto.getRandomValues(new Uint32Array(1))[0];
  return min + (value % span);
}

function noStore(headers = {}) {
  return { ...headers, "Cache-Control": "no-store" };
}

function validReport(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return false;
  const keys = Object.keys(body).sort();
  if (keys.length !== 2 || keys[0] !== "count" || keys[1] !== "schema") return false;
  return body.schema === 1 && Number.isInteger(body.count) && body.count >= 1 && body.count <= MAX_REPORT;
}

export class ReportMixer {
  constructor(state, env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request) {
    const body = await request.json().catch(() => ({}));
    const count = Number.isInteger(body.count) ? body.count : 0;
    if (count < 1 || count > MAX_REPORT) return new Response(null, { status: 400 });

    await this.state.storage.transaction(async (storage) => {
      const pending = Number(await storage.get("pending")) || 0;
      await storage.put("pending", pending + count);
      const alarm = await storage.getAlarm();
      if (alarm === null) {
        await storage.setAlarm(Date.now() + randomDelay(MIN_FLUSH_MS, MAX_FLUSH_MS));
      }
    });

    return new Response(null, { status: 202, headers: noStore() });
  }

  async alarm() {
    const pending = Number(await this.state.storage.get("pending")) || 0;
    if (pending < 1) return;

    const count = Math.min(pending, MAX_REPORT);
    const headers = { "Content-Type": "application/json" };
    if (this.env.UPSTREAM_TOKEN) headers["X-H3-Relay-Token"] = this.env.UPSTREAM_TOKEN;

    let ok = false;
    try {
      const response = await fetch(this.env.COUNTER_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({ count, schema: 1 }),
        redirect: "error",
      });
      ok = response.ok;
    } catch {
      ok = false;
    }

    if (!ok) {
      await this.state.storage.setAlarm(Date.now() + randomDelay(RETRY_MIN_MS, RETRY_MAX_MS));
      return;
    }

    let remaining = 0;
    await this.state.storage.transaction(async (storage) => {
      const current = Number(await storage.get("pending")) || 0;
      remaining = Math.max(0, current - count);
      if (remaining > 0) await storage.put("pending", remaining);
      else await storage.delete("pending");
    });

    if (remaining > 0) {
      await this.state.storage.setAlarm(Date.now() + randomDelay(MIN_FLUSH_MS, MAX_FLUSH_MS));
    }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/healthz") {
      return Response.json({ ok: true }, { headers: noStore() });
    }

    if (request.method !== "POST" || url.pathname !== "/v1/report") {
      return new Response("Not found", { status: 404, headers: noStore() });
    }

    const declaredLength = Number(request.headers.get("content-length") || 0);
    if (declaredLength > MAX_BODY_BYTES) return new Response(null, { status: 413, headers: noStore() });

    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
      return new Response(null, { status: 413, headers: noStore() });
    }

    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return new Response(null, { status: 400, headers: noStore() });
    }

    if (!validReport(body)) return new Response(null, { status: 400, headers: noStore() });

    const id = env.REPORT_MIXER.idFromName("global");
    const mixer = env.REPORT_MIXER.get(id);

    // Build a brand-new internal request from the two allowed values only. No
    // client headers, IP metadata, cookies, user agent or request URL are copied.
    return mixer.fetch(new Request("https://mixer/enqueue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: body.count }),
    }));
  },
};
