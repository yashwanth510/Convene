# Deploy Convene

Repository: https://github.com/yashwanth510/Convene

The app is configured for Cloudflare Pages → Render → Neon. API keys stay on Render; only the public API URL goes into the frontend.

## 1. Backend: Render

1. Connect the GitHub repository in Render and create a **Blueprint** from render.yaml. Use the Free plan.
2. Supply DATABASE_URL from Neon's Connect dialog (PostgreSQL, SSL enabled).
3. Add GROQ_API_KEY and OPENROUTER_API_KEY. Add TAVILY_API_KEY for web search and MISTRAL_API_KEY if you want Mistral. Leave unused optional keys empty.
4. Set CORS_ORIGINS to a JSON array containing the exact frontend origin, for example `["https://convene.pages.dev"]`. Replace this example with your actual Pages address.
5. Render generates INVITE_CODE. Save it privately; account creation requires this code. It must be at least 16 characters.
6. Deploy. The Docker command starts one Uvicorn worker and the application creates missing database tables. Check `https://YOUR-SERVICE.onrender.com/api/health`.

If creating a web service manually, select Docker, repository root, Free plan, health path /api/health, and copy the environment variables from render.yaml. APP_ENV must be production. Do not add a second worker/replica.

## 2. Frontend: Cloudflare Pages

Connect the GitHub repository to a Pages project with these settings:

| Setting | Value |
| --- | --- |
| Production branch | main |
| Root directory | frontend |
| Build command | npm run build |
| Output directory | dist |
| NODE_VERSION | 22 |
| VITE_API_BASE | https://YOUR-SERVICE.onrender.com/api |

Deploy, then copy the actual Pages origin into Render's CORS_ORIGINS and redeploy the backend if it changed. For a custom domain, include its exact HTTPS origin too. Preview URLs are not automatically authorized.

Cloudflare's [Vite build guide](https://developers.cloudflare.com/pages/framework-guides/deploy-a-vite3-project/) documents the build command and output directory. VITE_API_BASE is compiled into the bundle: rebuild after changing it. Never add provider keys, DATABASE_URL, or INVITE_CODE to Pages build variables.

## 3. Check the hosted app

Create an account using the private invitation code. Ask a short question, check model perspectives, refresh to confirm persistence, test a follow-up, and export the conversation. Sign out and verify the workspace requires authentication. Check a second account cannot access the first account's conversation.

## Free hosting expectations

Render Free sleeps after 15 idle minutes and may take about a minute to wake. Its filesystem is ephemeral, so Neon is necessary for persistent hosted conversations. Render can also restart free services; saved partial answers survive, but an interrupted run needs a new user request. Free service hours and outbound traffic are limited. See [Render's current free-service limits](https://render.com/docs/free).

The existing working Groq and OpenRouter keys are enough to run a council. Tavily adds web evidence; it is optional. Free model endpoints can rate-limit or disappear, so available models are centralized in backend/config.py and provider failures degrade visibly.

## Credentials and database operations

.env and .env.deploy are ignored by Git. If using API-based deployment, place CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, and RENDER_API_KEY in .env.deploy, never in chat or tracked files. Tokens must have permission for the target accounts/projects.

Use Neon's dashboard for backups/restore and monitor storage quotas. Deleting a conversation removes its runs, messages, and events, but its daily usage entry remains to prevent quota bypass. Account deletion and retention need an operator-managed procedure until an administration interface is added.
