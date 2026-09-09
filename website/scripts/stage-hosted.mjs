#!/usr/bin/env node
// Stage Docusaurus `build/` the same way deploy-site.yml stages GitHub Pages:
// files go under /docs/ because docusaurus.config.ts sets baseUrl to `/docs/`,
// and llms.txt is duplicated at the site root for agents that probe there.

import { copyFileSync, cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const websiteDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const buildDir = join(websiteDir, "build");
const hostedDir = join(websiteDir, "hosted");
const hostedDocs = join(hostedDir, "docs");

if (!existsSync(buildDir)) {
  console.error("[stage-hosted] website/build is missing; run npm run build first");
  process.exit(1);
}

rmSync(hostedDir, { recursive: true, force: true });
mkdirSync(hostedDocs, { recursive: true });
cpSync(buildDir, hostedDocs, { recursive: true });

for (const name of ["llms.txt", "llms-full.txt"]) {
  const src = join(buildDir, name);
  if (existsSync(src)) {
    copyFileSync(src, join(hostedDir, name));
  }
}

console.log(`[stage-hosted] wrote ${hostedDir}`);
