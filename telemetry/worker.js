const GOATCOUNTER_STATS_URL = "https://h3-studio.goatcounter.com/api/v0/stats/total";
const GOATCOUNTER_PUBLIC_COUNTER = "https://h3-studio.goatcounter.com/counter/generated.json";
const COUNTER_START = "2026-08-19T00:00:00Z";
const STATS_CACHE_MS = 10_000;

let cachedTotal = null;
let cachedUntil = 0;
let inFlight = null;

function parsePublicCount(value) {
  const digits = String(value ?? "").replace(/[^0-9]/g, "");
  const total = Number(digits);
  return Number.isSafeInteger(total) && total >= 0 ? total : null;
}

async function fetchFreshTotal(env) {
  if (env.GOATCOUNTER_API_TOKEN) {
    const api = new URL(GOATCOUNTER_STATS_URL);
    api.searchParams.set("start", COUNTER_START);

    const response = await fetch(api, {
      headers: {
        Authorization: `Bearer ${env.GOATCOUNTER_API_TOKEN}`,
        "Content-Type": "application/json",
        "User-Agent": "H3-Studio-Badge/1",
      },
      cache: "no-store",
    });

    if (response.ok) {
      const payload = await response.json();
      const total = Number(payload.total);
      if (Number.isSafeInteger(total) && total >= 0) return total;
    }
  }

  // Safe fallback: still read-only, but GoatCounter's public visitor counter may
  // be cached for much longer than the authenticated statistics API.
  const fallback = await fetch(GOATCOUNTER_PUBLIC_COUNTER, { cache: "no-store" });
  if (!fallback.ok) throw new Error(`GoatCounter counter returned ${fallback.status}`);
  const payload = await fallback.json();
  const total = parsePublicCount(payload.count);
  if (total === null) throw new Error("GoatCounter returned an invalid counter value");
  return total;
}

async function getTotal(env) {
  const now = Date.now();
  if (cachedTotal !== null && now < cachedUntil) return cachedTotal;
  if (inFlight) return inFlight;

  inFlight = fetchFreshTotal(env)
    .then((total) => {
      cachedTotal = total;
      cachedUntil = Date.now() + STATS_CACHE_MS;
      return total;
    })
    .finally(() => {
      inFlight = null;
    });

  return inFlight;
}

export function badgeSvg(total) {
  const accessibleLabel = "images generated";
  const value = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(total);
  const left = 106;
  const right = Math.max(54, 18 + value.length * 7);
  const width = left + right;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="28" role="img" aria-label="${accessibleLabel}: ${value}"><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-opacity=".12"/></linearGradient><clipPath id="r"><rect width="${width}" height="28" rx="6"/></clipPath><g clip-path="url(#r)"><rect width="${left}" height="28" fill="#171b1f"/><rect x="${left}" width="${right}" height="28" fill="#34d3b5"/><rect width="${width}" height="28" fill="url(#s)"/></g><g fill="none" stroke="#67e8d0" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="10" y="8" width="15" height="12" rx="2"/><circle cx="20.5" cy="11.5" r="1.3"/><path d="m12.5 18 3.8-4 2.7 2.6 1.7-1.6 2.2 3"/></g><g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="10"><text x="66" y="18">GENERATED</text><text x="${left + right / 2}" y="18" fill="#07120f">${value}</text></g></svg>`;
}

function publicHeaders(contentType) {
  return {
    "Content-Type": contentType,
    "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
    "CDN-Cache-Control": "no-store",
    Pragma: "no-cache",
    Expires: "0",
    "Access-Control-Allow-Origin": "*",
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Read-only counter proxy", { status: 405, headers: { Allow: "GET, HEAD" } });
    }

    if (url.pathname === "/healthz") {
      return Response.json(
        { ok: true, mode: "read-only-badge-proxy", goatcounter_api_configured: Boolean(env.GOATCOUNTER_API_TOKEN) },
        { headers: publicHeaders("application/json; charset=utf-8") },
      );
    }

    if (!["/badge.svg", "/v1/count", "/count.json"].includes(url.pathname)) {
      return new Response("Not found", { status: 404 });
    }

    try {
      const total = await getTotal(env);
      if (url.pathname === "/badge.svg") {
        return new Response(request.method === "HEAD" ? null : badgeSvg(total), {
          headers: publicHeaders("image/svg+xml; charset=utf-8"),
        });
      }

      const body = JSON.stringify({ reported_images_generated: total });
      return new Response(request.method === "HEAD" ? null : body, {
        headers: publicHeaders("application/json; charset=utf-8"),
      });
    } catch (_error) {
      return Response.json(
        { error: "counter temporarily unavailable" },
        { status: 503, headers: publicHeaders("application/json; charset=utf-8") },
      );
    }
  },
};
