const headers = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, PUT, OPTIONS",
  "access-control-allow-headers": "content-type, authorization, x-ajplay-admin"
};

function reply(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers });
}

function safeSegment(value) {
  return /^[a-zA-Z0-9_-]{1,100}$/.test(value);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });

    if (url.pathname === "/health" && request.method === "GET") {
      return reply({
        ok: true,
        service: "AJPLAY Catalog API",
        storageConfigured: Boolean(env.CATALOGS),
        authConfigured: Boolean(env.CATALOG_READ_TOKEN && env.CATALOG_WRITE_TOKEN)
      });
    }

    const match = url.pathname.match(/^\/v1\/catalog\/([a-zA-Z0-9_-]{1,100})$/);
    if (!match) return reply({ ok: false, error: "Not found" }, 404);
    const userId = match[1];
    const key = `users/${userId}/catalog.json`;

    if (!env.CATALOGS) return reply({ ok: false, error: "R2 binding CATALOGS is not configured" }, 503);

    if (request.method === "GET") {
      if (!env.CATALOG_READ_TOKEN || request.headers.get("authorization") !== `Bearer ${env.CATALOG_READ_TOKEN}`) {
        return reply({ ok: false, error: "Unauthorized" }, 401);
      }
      const object = await env.CATALOGS.get(key);
      if (!object) return reply({ ok: false, error: "Catalog not found" }, 404);
      return new Response(object.body, {
        headers: {
          ...headers,
          "content-type": "application/json; charset=utf-8",
          "etag": object.httpEtag,
          "x-catalog-updated": object.uploaded?.toISOString?.() || ""
        }
      });
    }

    if (request.method === "PUT") {
      if (!env.CATALOG_WRITE_TOKEN || request.headers.get("authorization") !== `Bearer ${env.CATALOG_WRITE_TOKEN}`) {
        return reply({ ok: false, error: "Unauthorized" }, 401);
      }
      const declaredLength = Number(request.headers.get("content-length") || 0);
      if (declaredLength > 25 * 1024 * 1024) return reply({ ok: false, error: "Catalog exceeds 25 MB test limit" }, 413);
      const raw = await request.text();
      if (!raw || raw.length > 25 * 1024 * 1024) return reply({ ok: false, error: "Catalog body is empty or too large" }, 413);
      let parsed;
      try { parsed = JSON.parse(raw); } catch { return reply({ ok: false, error: "Invalid JSON" }, 400); }
      if (!Array.isArray(parsed)) return reply({ ok: false, error: "Catalog root must be a JSON array" }, 400);
      await env.CATALOGS.put(key, raw, {
        httpMetadata: { contentType: "application/json; charset=utf-8" },
        customMetadata: { userId, records: String(parsed.length), format: "ajplay-catalog-v1" }
      });
      return reply({ ok: true, userId, records: parsed.length });
    }

    return reply({ ok: false, error: "Method not allowed" }, 405);
  }
};
