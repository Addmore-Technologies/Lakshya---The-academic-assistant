# Phase 1 — P0 Login and frontend connectivity

## Implemented in this phase

- Normalized `VITE_API_URL` (trims whitespace and trailing `/`) while retaining the existing Render default.
- Replaced the generic fetch failure text with an actionable connectivity message. It deliberately describes CORS as a possible cause because browsers do not expose enough information to distinguish CORS rejection from DNS/TLS/offline failures.
- Added accessible IDs, autocomplete hints, invalid-state metadata, and an assertive alert region to the login form.
- Extended the shared `Field` component to associate validation messages with inputs.
- Added API connectivity tests covering fetch rejection and ensuring HTTP 401 credential errors remain HTTP errors.
- Added/updated `frontend/.env.example`; no secrets belong in `VITE_*` variables.

## Files changed

- `frontend/src/lib/api.ts`
- `frontend/src/routes/index.tsx`
- `frontend/src/components/lk/ui.tsx`
- `frontend/src/test/api-network-error.test.ts` (new)
- `frontend/.env.example`

## Verification status

Automated tests and production build are **not verified in this delivery**. `npm ci --no-audit --no-fund` did not finish within the available execution window, so dependencies were removed from the package before creating the ZIP. Run locally:

```bash
cd frontend
npm ci
npm test
npm run build
```

## Deployment dependency (not a frontend code change)

The frontend cannot fix a server CORS allowlist. The backend deployment must allow this exact origin:

```env
FRONTEND_ORIGIN=https://tanstack-start-ts.aparnadhiraj12.workers.dev
```

If the backend supports multiple origins, retain all legitimate origins in its documented format. Do not use `*` with credentialed requests. After redeployment, verify the preflight:

```bash
curl -i -X OPTIONS \
  "https://lakshya-the-academic-assistant.onrender.com/auth/login" \
  -H "Origin: https://tanstack-start-ts.aparnadhiraj12.workers.dev" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Expected: successful preflight and `Access-Control-Allow-Origin` exactly matching the Cloudflare Pages/Workers frontend origin. Then manually test faculty and student login, protected route refresh, and logout.

## Git note

The supplied ZIP does not contain `.git` metadata. Extract this ZIP into a working directory, then connect it to the intended repository/branch only after checking and preserving any existing local changes. No commit or push was performed from this environment.
