import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://tripwire.test/", {
      headers: { accept: "text/html", host: "tripwire.test" },
    }),
    {
      ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the evidence-backed Tripwire experience", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Tripwire — Data systems that remember<\/title>/i);
  assert.match(html, /Data systems should/);
  assert.match(html, /remember/);
  assert.match(html, /TX-009/);
  assert.match(html, /LEARNED_PROTECTION_VIOLATED/);
  assert.match(html, /TRACE → TEST → WITNESS → ACT → IMMUNIZE/);
  assert.match(html, /https:\/\/tripwire\.test\/og\.png/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/);
});

test("ships public evidence and removes all starter-preview dependencies", async () => {
  const [page, layout, packageJson, learnedPassport] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(
      new URL("../public/evidence/04-learned-catch-passport.json", import.meta.url),
      "utf8",
    ),
  ]);

  assert.match(page, /04-learned-catch-passport\.json/);
  assert.match(layout, /generateMetadata/);
  assert.match(layout, /x-forwarded-host/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(learnedPassport, /LEARNED_PROTECTION_VIOLATED/);
  await access(new URL("../public/og.png", import.meta.url));
  await assert.rejects(access(new URL("../app/_sites-preview", templateRoot)));
});
