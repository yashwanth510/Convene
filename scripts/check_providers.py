"""Minimal live provider checks; prints statuses, never credentials or raw errors."""

import argparse
import asyncio
import json
from datetime import datetime, timezone
import httpx
from backend.config import config
from backend.llm.gateway import BASES


async def main(only=None):
    results = []
    async with httpx.AsyncClient(timeout=90) as client:
        for model in config.MODELS:
            provider = model["provider"]
            if only and only != provider:
                continue
            key = getattr(config, provider.upper() + "_API_KEY", "")
            if provider not in BASES or not key:
                results.append(
                    {
                        "provider": provider,
                        "model": model["api_model"],
                        "status": "not configured",
                    }
                )
                continue
            record = {"provider": provider, "model": model["api_model"]}
            try:
                r = await client.post(
                    BASES[provider] + "/chat/completions",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "model": model["api_model"],
                        "messages": [
                            {
                                "role": "user",
                                "content": "Reply with a short greeting, at most five words.",
                            }
                        ],
                        "max_tokens": 3000,
                        **({"enable_thinking": False} if provider == "qwen" else {}),
                    },
                )
                record["http"] = r.status_code
                if r.status_code == 200:
                    data = r.json()
                    choice = (data.get("choices") or [{}])[0]
                    record.update(
                        status="working"
                        if choice.get("message", {}).get("content")
                        and choice.get("finish_reason") == "stop"
                        else "no complete answer",
                        has_content=bool(choice.get("message", {}).get("content")),
                        finish_reason=choice.get("finish_reason"),
                        actual_model=data.get("model"),
                    )
                else:
                    record["status"] = {
                        401: "invalid credentials",
                        403: "access denied",
                        402: "billing required",
                        404: "model unavailable",
                        429: "rate limited; key validity not conclusive",
                    }.get(r.status_code, "provider error")
            except (httpx.HTTPError, ValueError):
                record["status"] = "connection or response error"
            results.append(record)
        if config.TAVILY_API_KEY and only in (None, "tavily"):
            try:
                r = await client.post(
                    "https://api.tavily.com/search",
                    headers={"Authorization": "Bearer " + config.TAVILY_API_KEY},
                    json={
                        "query": "Sakana Fugu",
                        "max_results": 1,
                        "search_depth": "basic",
                    },
                )
                results.append(
                    {
                        "provider": "tavily",
                        "http": r.status_code,
                        "has_results": bool(r.json().get("results"))
                        if r.status_code == 200
                        else False,
                    }
                )
            except (httpx.HTTPError, ValueError):
                results.append(
                    {"provider": "tavily", "status": "connection or response error"}
                )
    print(
        json.dumps(
            {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["groq", "openrouter", "qwen", "tavily"])
    asyncio.run(main(parser.parse_args().provider))
