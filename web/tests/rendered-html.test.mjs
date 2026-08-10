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
  assert.match(html, /SAFE_WITHIN_SCOPE/);
  assert.match(html, /NATIVE DATAHUB/);
  assert.match(html, /DataHub Assertion/);
  assert.match(html, /DataHub Incident/);
  assert.match(html, /SKU-0102/);
  assert.match(html, /ONE ENGINE · TWO DOMAINS/);
  assert.match(html, /fraud-risk-calibrator\/2\.0\.0/);
  assert.match(html, /6a71fb58/);
  assert.match(html, /TRACE → TEST → WITNESS → ACT → IMMUNIZE/);
  assert.match(html, /https:\/\/tripwire\.test\/og-v2\.png/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Starter Project/);
});

test("ships public evidence and removes all starter-preview dependencies", async () => {
  const [
    page,
    layout,
    packageJson,
    learnedPassport,
    safePassport,
    governanceSummary,
    inventorySummary,
  ] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(
      new URL("../public/evidence/live-v2-related-catch-passport.json", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../public/evidence/live-v2-safe-control-passport.json", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../public/evidence/native-governance-summary.json", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../public/evidence/inventory-slice-summary.json", import.meta.url),
      "utf8",
    ),
  ]);

  assert.match(page, /live-v2-related-catch-passport\.json/);
  assert.match(page, /live-v2-safe-control-passport\.json/);
  assert.match(layout, /generateMetadata/);
  assert.match(layout, /x-forwarded-host/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(learnedPassport, /LEARNED_PROTECTION_VIOLATED/);
  assert.match(safePassport, /SAFE_WITHIN_SCOPE/);
  assert.match(safePassport, /6a71fb58ee19d2c2971a12c36c81b7e8d48972bd/);
  assert.match(governanceSummary, /tripwire-protection-witness-tx-009-v1/);
  assert.match(governanceSummary, /"incident_state": "ACTIVE"/);
  assert.match(inventorySummary, /SKU-0102/);
  await access(new URL("../public/og-v2.png", import.meta.url));
  await assert.rejects(access(new URL("../app/_sites-preview", templateRoot)));
});
