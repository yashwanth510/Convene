# Deployment guide

Deploy the frontend on Cloudflare Pages, the backend on Render Free, and persistent data on Neon. The repository already contains the Dockerfile and Render configuration. You will create the hosted services through their dashboards.

## Before deployment

1. Run the local checks in the [README](../README.md#validation).
2. Push the repository to [GitHub](https://github.com/yashwanth510/Convene).
3. Keep the Neon DATABASE_URL and provider keys in your local .env until you copy them into Render's environment settings. Never add them to GitHub files or frontend variables.

## 1. Deploy the backend on Render

In the [Render dashboard](https://dashboard.render.com/), choose **New → Web Service**, connect GitHub, and select Convene.

| Setting | Value |
| --- | --- |
| Branch | main |
| Language/runtime | Docker |
| Root directory | Leave empty; use the repository root |
| Dockerfile path | ./Dockerfile |
| Instance type | Free |
| Health check path | /api/health |

Add these environment variables before deploying:

| Variable | Value |
| --- | --- |
| APP_ENV | production |
| DEBUG | false |
| DATABASE_URL | Your Neon PostgreSQL connection string, including SSL parameters |
| GROQ_API_KEY | Your Groq key |
| OPENROUTER_API_KEY | Your OpenRouter key |
| QWEN_API_KEY | Your working QwenCloud key |
| QWEN_BASE_URL | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 |
| QWEN_MODEL | qwen-plus |
| TAVILY_API_KEY | Your Tavily key; optional if you do not use web search |
| INVITE_CODE | A private random value of at least 16 characters |
| CORS_ORIGINS | An array with the exact Pages origin, such as ["https://YOUR-PROJECT.pages.dev"] |
| MAX_ACTIVE_RUNS | 2 |
| DEBATE_PANEL_SIZE | 4 |
| DAILY_RUN_LIMIT | 15 |
| RUN_CALL_BUDGET | 18 |
| RUN_TOKEN_BUDGET | 48000 |
| COMPLEX_REQUEST_TIMEOUT | 300 |

Generate an invitation code locally if needed:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

Keep the code private and share it only with people allowed to register.

Deploy and save the assigned backend URL, for example `https://convene-api-xxxx.onrender.com`. Open `https://YOUR-SERVICE.onrender.com/api/health`; a successful response includes `"status":"ok"` and `"database":"connected"`.

The application initializes missing database tables on startup. The Docker command uses one Uvicorn worker. Do not add workers or another backend instance.

Alternatively, choose **New → Blueprint**, connect this repository, and use [render.yaml](../render.yaml). The Blueprint contains the same configuration and generates INVITE_CODE; you still supply database/API secrets and CORS_ORIGINS.

## 2. Deploy the frontend on Cloudflare Pages

In the [Cloudflare dashboard](https://dash.cloudflare.com/), open **Workers & Pages**, create a **Pages** project, and connect the GitHub repository.

| Setting | Value |
| --- | --- |
| Production branch | main |
| Root directory | frontend |
| Framework preset | Vite, if offered |
| Build command | npm run build |
| Build output directory | dist |
| NODE_VERSION | 22 |
| VITE_API_BASE | https://YOUR-SERVICE.onrender.com/api |

VITE_API_BASE must include **/api**. Use the real Render URL, not the example. This value is public and compiled into the frontend; redeploy the frontend whenever it changes.

Save and deploy. Cloudflare will assign the actual Pages URL.

Provider keys, DATABASE_URL, and INVITE_CODE must **never** be added to Pages build variables. Only Render needs those secrets. See Cloudflare's [Vite deployment guide](https://developers.cloudflare.com/pages/framework-guides/deploy-a-vite3-project/) for its build settings.

## 3. Connect the deployed services

Copy the exact Pages origin into Render's CORS_ORIGINS, for example:

```json
["https://convene.pages.dev"]
```

Use no path or trailing slash. If your actual project has a different URL, use that URL. Save the change and redeploy the backend. Add a custom domain to the array only after you configure it.

The frontend talks directly to Render over HTTPS using an authenticated fetch stream. No Cloudflare Function or proxy service is required.

## 4. Verify the deployed application

1. Create an account using the invitation code.
2. Ask a Quick question with Web search off, then a Council question.
3. Check that the model list contains only the configured providers.
4. Turn Web search on for a current-information question and inspect Evidence.
5. Attach a document, ask a follow-up, refresh, and reopen the conversation.
6. Test export, cancellation, and sign-out.
7. Confirm a second account cannot open the first account's conversation.

A missing key disables that model. A provider error is shown as a warning; it does not produce a fabricated answer or confidence score.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Frontend loads but API calls fail | VITE_API_BASE includes /api, the backend health URL works, and CORS_ORIGINS matches the Pages origin |
| First request takes a while | Render Free may be waking from idle; wait and retry |
| Backend fails at startup | Neon URL, SSL, APP_ENV, invitation-code length, and HTTPS CORS origins |
| Qwen rejects authentication | QwenCloud uses the international base URL above; keys and regional endpoints must match |
| No sources appear | Web search is off, Tavily is unconfigured/unavailable, or no usable source was returned |
| An answer is interrupted after deployment | Restart recovery retains saved progress; submit a new question to run again |

## Free hosting and data

[Render Free](https://render.com/docs/free) can sleep after 15 idle minutes and can restart at any time. Its local filesystem is temporary. Neon is therefore required for persistent hosted conversations; do not use SQLite on Render.

Provider APIs have their own quotas and billing. A free hosting plan does not make every model call free. Monitor provider usage, Render limits, and Neon storage.

Use the Neon dashboard for backups and recovery. Schema initialization creates missing tables; future changes to existing columns need a migration. This deployment supports one backend process, not concurrent replicas or overlapping rolling deployments.

No service has to be created by a command in this guide. The GitHub push, Render deployment, and Cloudflare deployment remain actions you perform through your terminal and dashboards.
