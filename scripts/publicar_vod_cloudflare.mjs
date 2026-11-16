import { readFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

const token=process.env.CLOUDFLARE_API_TOKEN, account=process.env.CLOUDFLARE_ACCOUNT_ID, project=process.env.CLOUDFLARE_PAGES_PROJECT;
if(!token||!account||!project) throw new Error("Faltan secretos/configuración de Cloudflare.");
const api="https://api.cloudflare.com/client/v4";
async function cf(endpoint,options={},bearer=token){
 const r=await fetch(api+endpoint,{...options,headers:{Authorization:`Bearer ${bearer}`,...(options.headers||{})}});
 const d=await r.json().catch(()=>({}));
 if(!r.ok||d.success===false) throw new Error((d.errors||[]).map(x=>x.message).join("; ")||d.message||`Cloudflare HTTP ${r.status}`);
 return d;
}
async function walk(dir){const out=[];for(const e of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())out.push(...await walk(p));else if(e.isFile()&&e.name==="VOD.txt")out.push(p);}return out;}
const paths=(await walk("usuarios")).sort();
if(!paths.length)throw new Error("No hay usuarios/{cliente_id}/VOD.txt.");
const assets=[];
for(const p of paths){const body=await readFile(p),txt=body.toString("utf8");if(!txt.startsWith("#EXTM3U")||!txt.includes("#EXTINF"))throw new Error(`${p} no es M3U válido.`);assets.push({path:"/"+p.replaceAll("\\","/"),body,hash:createHash("sha256").update(body).digest("hex")});}
const ut=await cf(`/accounts/${account}/pages/projects/${project}/upload-token`),jwt=ut.result?.jwt;
if(!jwt)throw new Error("Cloudflare no entregó token temporal.");
const hashes=assets.map(a=>a.hash),missing=await cf("/pages/assets/check-missing",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({hashes})},jwt);
const missingSet=new Set(missing.result||[]),upload=assets.filter(a=>missingSet.has(a.hash));
for(let i=0;i<upload.length;i+=20)await cf("/pages/assets/upload",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(upload.slice(i,i+20).map(a=>({key:a.hash,value:a.body.toString("base64"),metadata:{contentType:"audio/x-mpegurl; charset=utf-8"},base64:true})))},jwt);
await cf("/pages/assets/upsert-hashes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({hashes})},jwt);
// Conservar los demás recursos del deployment y sustituir solo los VOD por cliente.
const prev=await cf(`/accounts/${account}/pages/projects/${project}/deployments?per_page=1`),prevId=prev.result?.[0]?.id,manifest={};
if(prevId){const old=await cf(`/accounts/${account}/pages/projects/${project}/deployments/${prevId}`);for(const [p,v] of Object.entries(old.result?.files||{})){const key=p.startsWith("/")?p:"/"+p;if(!/^\/usuarios\/[^/]+\/VOD\.txt$/.test(key))manifest[key]=String(v);}}
for(const a of assets)manifest[a.path]=a.hash;
const form=new FormData();form.append("manifest",JSON.stringify(manifest));form.append("branch","main");
const dep=await cf(`/accounts/${account}/pages/projects/${project}/deployments`,{method:"POST",body:form}),id=dep.result?.id;
if(!id)throw new Error("Cloudflare no devolvió ID de deployment.");
let cur=dep.result;
for(let i=0;i<60;i++){const st=String(cur.latest_stage?.status||"").toLowerCase();if(st==="success")break;if(["failure","failed","canceled","cancelled"].includes(st))throw new Error("Deployment fallido: "+st);await new Promise(r=>setTimeout(r,3000));cur=(await cf(`/accounts/${account}/pages/projects/${project}/deployments/${id}`)).result||cur;}
if(String(cur.latest_stage?.status||"").toLowerCase()!=="success")throw new Error("Cloudflare no confirmó el deployment.");
console.log(`Publicados ${assets.length} catálogos VOD independientes.`);for(const a of assets)console.log(`https://${project}.pages.dev${a.path}`);
