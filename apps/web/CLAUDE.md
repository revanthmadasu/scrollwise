# Claude Code instructions for `apps/web`

The ScrollWise frontend: an Instagram-style learning feed. A React SPA that
talks to `apps/api`.

## Architecture decisions already made — don't relitigate

1. **React + TypeScript + Vite** (SPA, not SSR). The app is fully
   authenticated, so there's no SEO/SSR need. Dev server runs on `:5173`, which
   the API already allows via CORS.

2. **Data layer = TanStack Query** over a thin typed fetch client
   (`src/api/client.ts`). The client holds the JWT pair in `localStorage` and
   transparently refreshes on a 401. Don't scatter `fetch` calls in components —
   add a method to `api` and call it through a query/mutation.

3. **Types mirror the API by hand** in `src/api/types.ts`. When `apps/api`
   publishes its OpenAPI spec to `packages/contract`, replace these with
   generated types rather than drifting.

4. **The feed is server-stateful.** `GET /feed` advances progress and marks
   posts seen on the server, so the client just calls it repeatedly (infinite
   query) and appends — there's no client-side cursor. Don't add one.

5. **Styling is hand-written CSS** in `src/index.css` (CSS variables, no
   framework). Keep the dark, card-based aesthetic.

6. **Google sign-in is optional.** The button only renders when
   `VITE_GOOGLE_CLIENT_ID` is set (`src/components/GoogleButton.tsx`).

## Node version

The repo's default `node` may be old (the machine this was built on had Node 14,
which Vite 5 can't use). Build/run with Node 18+ (e.g. `nvm use 22`). The
preview launcher in `.claude/launch.json` points directly at a Node 22 binary
for this reason.

## Layout

```
src/
  api/         types.ts (API mirrors) + client.ts (fetch + auth/refresh)
  auth/        AuthContext (login/register/google/logout, user resolution)
  components/  Layout, ProtectedRoute, PostCard, TestCard, ReactionBar, GoogleButton
  pages/       Login, Register, Feed, Discover (prompts), Interests, Progress
  App.tsx      routes (+ protected shell)
  main.tsx     QueryClient + render
  index.css    all styles
```

## Running

```bash
npm install
cp .env.example .env          # VITE_API_BASE, optional VITE_GOOGLE_CLIENT_ID
npm run dev                    # http://localhost:5173
npm run build                  # tsc -b && vite build  (CI gate)
```

`npm run build` type-checks; keep it green.
