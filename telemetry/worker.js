export class GenerationCounter {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/increment") {
      const body = await request.json().catch(() => ({}));
      const increment = Number.isInteger(body.count) ? body.count : 0;
      if (increment < 1 || increment > 100) return Response.json({ error: "invalid count" }, { status: 400 });
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

function badgeSvg(total) {
  const label = "reported images";
  const value = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(total);
  const left = 108;
  const right = Math.max(54, 18 + value.length * 7);
  const width = left + right;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="28" role="img" aria-label="${label}: ${value}"><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-opacity=".12"/></linearGradient><clipPath id="r"><rect width="${width}" height="28" rx="6"/></clipPath><g clip-path="url(#r)"><rect width="${left}" height="28" fill="#171b1f"/><rect x="${left}" width="${right}" height="28" fill="#34d3b5"/><rect width="${width}" height="28" fill="url(#s)"/></g><g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="10"><text x="${left / 2}" y="18">${label}</text><text x="${left + right / 2}" y="18" fill="#07120f">${value}</text></g></svg>`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const id = env.GENERATION_COUNTER.idFromName("global");
    const counter = env.GENERATION_COUNTER.get(id);

    if (request.method === "POST" && url.pathname === "/v1/report") {
      if (Number(request.headers.get("content-length") || 0) > 128) return new Response(null, { status: 413 });
      const body = await request.json().catch(() => ({}));
      const count = Number.isInteger(body.count) ? body.count : 0;
      if (body.schema !== 1 || count < 1 || count > 100) return Response.json({ error: "invalid report" }, { status: 400 });
      return counter.fetch(new Request("https://counter/increment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count }),
      }));
    }

    if (request.method === "GET" && ["/v1/count", "/badge.svg"].includes(url.pathname)) {
      const response = await counter.fetch("https://counter/value");
      const { total = 0 } = await response.json();
      if (url.pathname === "/badge.svg") {
        return new Response(badgeSvg(total), {
          headers: { "Content-Type": "image/svg+xml; charset=utf-8", "Cache-Control": "public, max-age=300" },
        });
      }
      return Response.json({ reported_images_generated: total }, { headers: { "Cache-Control": "public, max-age=60" } });
    }

    return new Response("Not found", { status: 404 });
  },
};
