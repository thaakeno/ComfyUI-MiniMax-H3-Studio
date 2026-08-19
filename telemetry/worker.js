export class GenerationCounter {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/increment") {
      const body = await request.json().catch(() => ({}));
      const increment = Number.isInteger(body.count) ? body.count : 0;
      if (increment < 1 || increment > 100) {
        return Response.json({ error: "invalid count" }, { status: 400 });
      }

      const total = await this.state.storage.transaction(async (storage) => {
        const current = Number(await storage.get("total")) || 0;
        const next = current + increment;
        await storage.put("total", next);
        return next;
      });
      return Response.json({ total });
    }

    const total = Number(await this.state.storage.get("total")) || 0;
    return Response.json({ total });
  }
}

const GOATCOUNTER_COUNTER = "https://h3-studio.goatcounter.com/counter/generated.json";

function badgeSvg(total) {
  const value = new Intl.NumberFormat("en-US").format(total);
  const left = 106;
  const right = Math.max(60, 20 + value.length * 7);
  const width = left + right;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="28" role="img" aria-label="images generated: ${value}"><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-opacity=".12"/></linearGradient><clipPath id="r"><rect width="${width}" height="28" rx="6"/></clipPath><g clip-path="url(#r)"><rect width="${left}" height="28" fill="#171b1f"/><rect x="${left}" width="${right}" height="28" fill="#34d3b5"/><rect width="${width}" height="28" fill="url(#s)"/></g><g fill="none" stroke="#67e8d0" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="10" y="8" width="15" height="12" rx="2"/><circle cx="20.5" cy="11.5" r="1.3"/><path d="m12.5 18 3.8-4 2.7 2.6 1.7-1.6 2.2 3"/></g><g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="10"><text x="66" y="18">GENERATED</text><text x="${left + right / 2}" y="18" fill="#07120f">${value}</text></g></svg>`;
}

async function freshGoatCounterTotal() {
  const url = new URL(GOATCOUNTER_COUNTER);
  // GoatCounter's public visitor counter can otherwise be cached for hours.
  // A per-request query key forces a fresh upstream lookup for the badge.
  url.searchParams.set("h3_fresh", String(Date.now()));

  const response = await fetch(url, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  if (!response.ok) throw new Error(`GoatCounter returned ${response.status}`);

  const payload = await response.json();
  const digits = String(payload.count ?? "").replace(/[^0-9]/g, "");
  const total = Number(digits);
  if (!Number.isSafeInteger(total) || total < 0) throw new Error("invalid GoatCounter count");
  return total;
}

function noCacheHeaders(contentType) {
  return {
    "Content-Type": contentType,
    "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
    "CDN-Cache-Control": "no-store",
    Pragma: "no-cache",
    Expires: "0",
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const id = env.GENERATION_COUNTER.idFromName("global");
    const counter = env.GENERATION_COUNTER.get(id);

    // Legacy compatibility only. Current H3 Studio builds report directly to
    // GoatCounter; old installed versions may still call this endpoint.
    if (request.method === "POST" && url.pathname === "/v1/report") {
      if (Number(request.headers.get("content-length") || 0) > 128) {
        return new Response(null, { status: 413 });
      }
      const body = await request.json().catch(() => ({}));
      const count = Number.isInteger(body.count) ? body.count : 0;
      if (body.schema !== 1 || count < 1 || count > 100) {
        return Response.json({ error: "invalid report" }, { status: 400 });
      }
      return counter.fetch(new Request("https://counter/increment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count }),
      }));
    }

    // Keep the legacy total readable so old-version delta imports can be done
    // after the GoatCounter cutover.
    if (request.method === "GET" && url.pathname === "/v1/count") {
      const response = await counter.fetch("https://counter/value");
      const { total = 0 } = await response.json();
      return Response.json(
        { reported_images_generated: total },
        { headers: { "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate" } },
      );
    }

    // README display only: always source the number from GoatCounter, never the
    // legacy Durable Object. GitHub recommends no-cache for changing images.
    if ((request.method === "GET" || request.method === "HEAD") && url.pathname === "/badge.svg") {
      try {
        const total = await freshGoatCounterTotal();
        return new Response(request.method === "HEAD" ? null : badgeSvg(total), {
          headers: noCacheHeaders("image/svg+xml; charset=utf-8"),
        });
      } catch (_error) {
        return new Response(request.method === "HEAD" ? null : badgeSvg(0), {
          status: 503,
          headers: noCacheHeaders("image/svg+xml; charset=utf-8"),
        });
      }
    }

    return new Response("Not found", { status: 404 });
  },
};
