# Routing Matrix

This is the canonical host/path routing model for the split product setup.

For deploys, the canonical public URLs are configured with `AGENTIC_PUBLIC_BASE_URL` and
`LETTERS_PUBLIC_BASE_URL`. The older host-map fallback is still available for local testing.

## Public Tenant Routes

### Assistant Host

- staging: `https://st1-agentic.gridics.com/{jurisdiction-public-path-alias}`
- prod: `https://agentic.gridics.com/{jurisdiction-public-path-alias}`

Examples:

- `https://st1-agentic.gridics.com/us/fl/miami`
- `https://agentic.gridics.com/us/fl/miami`

Behavior:

- the alias root opens the assistant experience

### Zoning Letters Host

- staging: `https://st1-zvl.gridics.com/{jurisdiction-public-path-alias}`
- prod: `https://zvl.gridics.com/{jurisdiction-public-path-alias}`

Examples:

- `https://st1-zvl.gridics.com/us/fl/miami`
- `https://zvl.gridics.com/us/fl/miami`

Behavior:

- the alias root opens the zoning letters experience

## Tenant Admin Routes

Tenant admin is available on both product hosts and always uses `/admin/{alias}`.

### Assistant Host Admin

- staging: `https://st1-agentic.gridics.com/admin/{jurisdiction-public-path-alias}`
- prod: `https://agentic.gridics.com/admin/{jurisdiction-public-path-alias}`

Examples:

- `https://st1-agentic.gridics.com/admin/us/fl/miami`
- `https://agentic.gridics.com/admin/us/fl/miami`

### Zoning Letters Host Admin

- staging: `https://st1-zvl.gridics.com/admin/{jurisdiction-public-path-alias}`
- prod: `https://zvl.gridics.com/admin/{jurisdiction-public-path-alias}`

Examples:

- `https://st1-zvl.gridics.com/admin/us/fl/miami`
- `https://zvl.gridics.com/admin/us/fl/miami`

## Super Admin Routes

Super admin remains host-agnostic and can be served from either product host:

- `https://st1-agentic.gridics.com/super-admin/...`
- `https://st1-zvl.gridics.com/super-admin/...`
- `https://agentic.gridics.com/super-admin/...`
- `https://zvl.gridics.com/super-admin/...`

## Notes

- On `agentic.*`, `/{alias}` rewrites to the assistant app.
- On `zvl.*`, `/{alias}` stays on the zoning letters app.
- On both hosts, `/admin/{alias}` resolves tenant admin for the same jurisdiction alias.
- Internal Clerk org-switching routes still use `/_internal/{orgId}/...` behind the scenes, but the public-facing canonical admin routes are `/admin/{alias}`.

## Local Testing With Hosts Files

To test the split host routing locally, map local hostnames to `127.0.0.1` and run the frontend on port `3001`.

Recommended local hostnames:

- `st1-agentic.gridics.local`
- `st1-zvl.gridics.local`

These work well because the frontend routing logic detects:

- `agentic.` => assistant product
- `zvl.` => zoning letters product

### Linux

1. Edit `/etc/hosts` as root:

```bash
sudo nano /etc/hosts
```

2. Add:

```txt
127.0.0.1 st1-agentic.gridics.local
127.0.0.1 st1-zvl.gridics.local
```

3. Save the file.

4. Start the backend and frontend locally.

Frontend:

```bash
cd /home/ben/gprojects/gridics-zoning-cookbook/uzone/frontend
npm run dev
```

5. Open these URLs in the browser:

- Assistant tenant route:
  - `http://st1-agentic.gridics.local:3001/us/fl/miami`
- Letters tenant route:
  - `http://st1-zvl.gridics.local:3001/us/fl/miami`
- Assistant-host admin:
  - `http://st1-agentic.gridics.local:3001/admin/us/fl/miami`
- Letters-host admin:
  - `http://st1-zvl.gridics.local:3001/admin/us/fl/miami`
- Super admin:
  - `http://st1-agentic.gridics.local:3001/super-admin`
  - `http://st1-zvl.gridics.local:3001/super-admin`

### Windows

1. Open Notepad as Administrator.

2. Open this file:

```txt
C:\Windows\System32\drivers\etc\hosts
```

3. Add:

```txt
127.0.0.1 st1-agentic.gridics.local
127.0.0.1 st1-zvl.gridics.local
```

4. Save the file.

5. Start the backend and frontend locally.

Frontend:

```powershell
cd C:\path\to\gridics-zoning-cookbook\uzone\frontend
npm run dev
```

6. Open these URLs in the browser:

- `http://st1-agentic.gridics.local:3001/us/fl/miami`
- `http://st1-zvl.gridics.local:3001/us/fl/miami`
- `http://st1-agentic.gridics.local:3001/admin/us/fl/miami`
- `http://st1-zvl.gridics.local:3001/admin/us/fl/miami`
- `http://st1-agentic.gridics.local:3001/super-admin`
- `http://st1-zvl.gridics.local:3001/super-admin`

### Expected Results

- `st1-agentic.gridics.local:3001/{alias}` opens the assistant experience
- `st1-zvl.gridics.local:3001/{alias}` opens the zoning letters experience
- both `/admin/{alias}` URLs open tenant admin for the same jurisdiction
- both `/super-admin/...` URLs open the shared super admin area

### Quick Verification

If you want a fast code-level check before opening the browser:

```bash
cd /home/ben/gprojects/gridics-zoning-cookbook/uzone/frontend
npm test
```

That verifies the host-aware routing helpers for:

- host detection
- `/{alias}` routing
- `/admin/{alias}` formatting
- cross-host link generation
