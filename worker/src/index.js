const cors = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, PUT, OPTIONS",
  "access-control-allow-headers": "content-type, authorization"
};
const json = (body, status = 200) => new Response(JSON.stringify(body), {status, headers:cors});
const segment = /^[a-zA-Z0-9_-]{1,100}$/;
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null,{status:204,headers:cors});
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ok:true,service:"AJPLAY Catalog API",storageConfigured:!!env.CATALOGS,authConfigured:!!env.CATALOG_READ_TOKEN && !!env.CATALOG_WRITE_TOKEN});
    }
    const match = url.pathname.match(/^\/v1\/catalog\/([^/]+)\/([^/]+)$/);
    if (!match || !segment.test(match[1]) || !segment.test(match[2])) return json({ok:false,error:"Not found"},404);
    if (!env.CATALOGS) return json({ok:false,error:"KV binding CATALOGS missing"},503);
    const [, clientId, serverId] = match;
    const key = `client:${clientId}:server:${serverId}:catalog:v1`;
    if (request.method === "PUT") {
      if (!env.CATALOG_WRITE_TOKEN || request.headers.get("authorization") !== `Bearer ${env.CATALOG_WRITE_TOKEN}`) return json({ok:false,error:"Unauthorized"},401);
      const raw = await request.text();
      if (!raw || raw.length > 24 * 1024 * 1024) return json({ok:false,error:"JSON empty or exceeds 24 MiB"},413);
      let catalog;
      try { catalog = JSON.parse(raw); } catch { return json({ok:false,error:"Invalid JSON"},400); }
      if (!catalog || typeof catalog !== "object" || Array.isArray(catalog) ||
          !Array.isArray(catalog.categories) || !Array.isArray(catalog.streams) ||
          String(catalog.client_id) !== clientId || String(catalog.server_id) !== serverId) {
        return json({ok:false,error:"Expected original categories and streams for the matching client/server"},400);
      }
      await env.CATALOGS.put(key, raw, {metadata:{clientId,serverId,categories:catalog.categories.length,streams:catalog.streams.length,format:"ajplay-v1",publishedAt:new Date().toISOString()}});
      return json({ok:true,clientId,serverId,categories:catalog.categories.length,streams:catalog.streams.length});
    }
    if (request.method === "GET") {
      if (!env.CATALOG_READ_TOKEN || request.headers.get("authorization") !== `Bearer ${env.CATALOG_READ_TOKEN}`) return json({ok:false,error:"Unauthorized"},401);
      const value = await env.CATALOGS.get(key);
      if (value === null) return json({ok:false,error:"Catalog not found"},404);
      return new Response(value,{status:200,headers:{...cors,"content-type":"application/json; charset=utf-8"}});
    }
    return json({ok:false,error:"Method not allowed"},405);
  }
};
