/**
 * Package the existing Vite build into a self-contained Sites Worker ESM entry.
 * The Sites starter copies one worker file, so static assets are embedded here.
 * Run after npm run build. This stages source locally; it never registers/publishes.
 */
import { readFile, readdir, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const source = path.join(root, "frontend/dist");
const output = path.join(root, "artifacts/sites/worker");
const assets = {};
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};
async function collect(directory) {
  // Walk built files recursively and retain each URL path and content type.
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) await collect(absolute);
    else
      assets["/" + path.relative(source, absolute).split(path.sep).join("/")] =
        {
          type: types[path.extname(entry.name)] || "application/octet-stream",
          body: (await readFile(absolute)).toString("base64"),
        };
  }
}
await collect(source);
if (!assets["/index.html"]) throw new Error("Build frontend/dist first.");
let gateway = await readFile(path.join(root, "deploy/sites/worker.js"), "utf8");
// Wrap the gateway with embedded static assets; this generates source, not a hosted Site.
gateway = gateway.replace("export default {", "const gateway = {");
const wrapper = `
const embedded = ${JSON.stringify(assets)};
const staticAssets = {
  async fetch(request) {
    if (!["GET", "HEAD"].includes(request.method)) return new Response("Method not allowed", {status:405});
    const name = new URL(request.url).pathname;
    const asset = embedded[name] || embedded["/index.html"];
    const bytes = request.method === "HEAD" ? null : Uint8Array.from(atob(asset.body), c => c.charCodeAt(0));
    return new Response(bytes, {headers:{"Content-Type":asset.type,"X-Content-Type-Options":"nosniff","Cache-Control":name.startsWith("/assets/") ? "public,max-age=31536000,immutable" : "no-cache"}});
  }
};
export default {fetch(request, env) {return gateway.fetch(request, {...env, ASSETS:staticAssets});}};
`;
await mkdir(output, { recursive: true });
await writeFile(path.join(output, "index.js"), gateway + wrapper);
console.log(
  `Staged ${Object.keys(assets).length} assets at artifacts/sites/worker/index.js; no Site created or deployed.`,
);
