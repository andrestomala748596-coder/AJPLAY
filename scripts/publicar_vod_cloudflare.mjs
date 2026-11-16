import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

const token = process.env.CLOUDFLARE_API_TOKEN;
const account = process.env.CLOUDFLARE_ACCOUNT_ID;
const project = process.env.CLOUDFLARE_PAGES_PROJECT;
if (!token || !account || !project) throw new Error("Faltan secretos/configuración de Cloudflare.");
const api = "https://api.cloudflare.com/client/v4";
async function cf(path, options = {}, bearer = token) {
  const response = await fetch(api + path, {
    ...options,
    headers: { Authorization: `Bearer ${bearer}`, ...(options.headers || {}) }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    throw new Error((data.errors || []).map(x => x.message).join("; ") || data.message || `Cloudflare HTTP ${response.status}`);
  }
  return data;
}
const content = await readFile("VOD.txt");
if (!content.length) throw new Error("VOD.txt está vacío.");
const hash = createHash("sha256").update(content).digest("hex");
const uploadToken = await cf(`/accounts/${account}/pages/projects/${project}/upload-token`);
const jwt = uploadToken.result?.jwt;
if (!jwt) throw new Error("Cloudflare no entregó token temporal.");
const missing = await cf("/pages/assets/check-missing", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ hashes: [hash] })
}, jwt);
if ((missing.result || []).includes(hash)) {
  await cf("/pages/assets/upload", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify([{
      key: hash, value: content.toString("base64"),
      metadata: { contentType: "audio/x-mpegurl; charset=utf-8" }, base64: true
    }])
  }, jwt);
}
await cf("/pages/assets/upsert-hashes", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ hashes: [hash] })
}, jwt);

// Conservar todos los archivos del deployment anterior y sustituir solo /VOD.txt.
const previous = await cf(`/accounts/${account}/pages/projects/${project}/deployments?per_page=1`);
const previousId = previous.result?.[0]?.id;
const manifest = {};
if (previousId) {
  const old = await cf(`/accounts/${account}/pages/projects/${project}/deployments/${previousId}`);
  for (const [path, value] of Object.entries(old.result?.files || {})) {
    manifest[path.startsWith("/") ? path : "/" + path] = String(value);
  }
}
manifest["/VOD.txt"] = hash;
const form = new FormData();
form.append("manifest", JSON.stringify(manifest));
form.append("branch", "main");
const deployment = await cf(`/accounts/${account}/pages/projects/${project}/deployments`, {
  method: "POST", body: form
});
const id = deployment.result?.id;
if (!id) throw new Error("Cloudflare no devolvió ID de deployment.");
let current = deployment.result;
for (let i = 0; i < 60; i++) {
  const status = String(current.latest_stage?.status || "").toLowerCase();
  if (status === "success") break;
  if (["failure", "failed", "canceled", "cancelled"].includes(status)) {
    throw new Error("Deployment fallido: " + status);
  }
  await new Promise(resolve => setTimeout(resolve, 3000));
  current = (await cf(`/accounts/${account}/pages/projects/${project}/deployments/${id}`)).result || current;
}
if (String(current.latest_stage?.status || "").toLowerCase() !== "success") {
  throw new Error("Cloudflare no confirmó el deployment.");
}
console.log(`VOD publicado: https://${project}.pages.dev/VOD.txt`);
