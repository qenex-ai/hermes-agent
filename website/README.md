# Website

This website is built using [Docusaurus](https://docusaurus.io/), a modern static website generator.

## Installation

```bash
yarn
```

## Local Development

```bash
yarn start
```

This command starts a local development server and opens up a browser window. Most changes are reflected live without having to restart the server.

## Build

```bash
yarn build
```

This command generates static content into the `build` directory and can be served using any static contents hosting service.

## Deployment

NousResearch production docs still ship through GitHub Pages
(`.github/workflows/deploy-site.yml`). Vercel previews and CLI production
deploys use `.github/workflows/deploy-vercel.yml`: GitHub Actions runs the
Python skill-doc generators, `vercel build`, then `vercel deploy --prebuilt`.

Required repository secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
Point the Vercel project's Root Directory at `website`. Disable Vercel git
auto-deploy so a remote rebuild cannot skip the generators.

- Pull requests against `website/**` / `skills/**` → preview URL (commented on the PR)
- `main`, a published release, or `workflow_dispatch` → production

## Diagram Linting

CI runs `ascii-guard` to lint docs for ASCII box diagrams. Use Mermaid (````mermaid`) or plain lists/tables instead of ASCII boxes to avoid CI failures.
