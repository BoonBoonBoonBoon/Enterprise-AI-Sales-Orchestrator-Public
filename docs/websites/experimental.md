# Experimental Portals (apps/portal-experimental\*)

These folders are prototype/sandbox Next.js apps used for rapid UI iteration.

## Inventory

- `apps/portal-experimental`
- `apps/portal-experimental-2`
- `apps/portal-experimental-3`
- `apps/portal-experimental-4`

## Running locally

Each experimental portal defines its own dev port in its `package.json`.

Example (portal-experimental-4):

```bash
cd apps/portal-experimental-4
npm install
npm run dev  # runs: next dev -p 3004
```

If you standardize ports for these, document them here (and keep `package.json` scripts aligned).
