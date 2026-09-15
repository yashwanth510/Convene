import asyncio
import io
import json
import time
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Header
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import text
from backend.api.auth import current_user
from backend.api.schemas import RunRequest, Feedback
from backend.config import config
from backend.storage.database import TERMINAL
from backend.utils.document_parser import parse_document

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    try:
        async with request.app.state.db.engine.connect() as c:
            await c.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database temporarily unavailable") from None
    return {
        "status": "ok",
        "app": "Convene",
        "version": "1.0.0",
        "database": "connected",
    }


@router.get("/models")
async def models(request: Request, user=Depends(current_user)):
    return request.app.state.gateway.catalog()


@router.get("/settings")
async def settings(user=Depends(current_user)):
    return {
        "panel_size": config.DEBATE_PANEL_SIZE,
        "debate_rounds": 2,
        "mode": "auto",
        "daily_run_limit": config.DAILY_RUN_LIMIT,
        "request_timeout": config.COMPLEX_REQUEST_TIMEOUT,
        "token_budget": config.RUN_TOKEN_BUDGET,
    }


@router.get("/telemetry")
async def telemetry(request: Request, user=Depends(current_user)):
    return await request.app.state.db.telemetry(user["id"])


@router.post("/conversations", status_code=201)
async def create_conversation(request: Request, user=Depends(current_user)):
    return await request.app.state.db.create_conversation(user["id"])


@router.get("/conversations")
async def list_conversations(request: Request, user=Depends(current_user)):
    return await request.app.state.db.list_conversations(user["id"])


@router.get("/conversations/{cid}")
async def get_conversation(cid: str, request: Request, user=Depends(current_user)):
    return await request.app.state.db.conversation(user["id"], cid)


@router.delete("/conversations/{cid}", status_code=204)
async def delete_conversation(cid: str, request: Request, user=Depends(current_user)):
    await request.app.state.db.delete_conversation(user["id"], cid)


@router.post("/conversations/{cid}/runs", status_code=202)
async def start_run(
    cid: str, body: RunRequest, request: Request, user=Depends(current_user)
):
    active = {m["id"] for m in config.MODELS if m["status"] == "active"}
    if not body.content.strip():
        raise HTTPException(422, "Enter a question")
    if body.enabled_models is not None and (
        not body.enabled_models or not set(body.enabled_models) <= active
    ):
        raise HTTPException(422, "Select at least one supported active model")
    if body.chairman_model and (
        body.chairman_model not in active
        or (
            body.enabled_models is not None
            and body.chairman_model not in body.enabled_models
        )
    ):
        raise HTTPException(422, "The synthesizer must be one of your enabled models")
    if len(request.app.state.runs.tasks) >= config.MAX_ACTIVE_RUNS * 4:
        raise HTTPException(429, "The queue is full. Please try again shortly.")
    row, created = await request.app.state.db.create_run(
        user["id"], cid, body.model_dump(), config.DAILY_RUN_LIMIT
    )
    if created:
        request.app.state.runs.start(row)
    return {"id": row["id"], "status": row["status"], "conversation_id": cid}


@router.get("/runs/{rid}")
async def get_run(rid: str, request: Request, user=Depends(current_user)):
    row = await request.app.state.db.get_run(user["id"], rid)
    return {
        k: row[k]
        for k in ("id", "conversation_id", "status", "result", "event_seq", "feedback")
    }


@router.post("/runs/{rid}/cancel", status_code=204)
async def cancel_run(rid: str, request: Request, user=Depends(current_user)):
    await request.app.state.runs.cancel(user["id"], rid)


@router.post("/runs/{rid}/feedback", status_code=204)
async def feedback(
    rid: str, body: Feedback, request: Request, user=Depends(current_user)
):
    await request.app.state.db.feedback(user["id"], rid, body.value)


@router.get("/runs/{rid}/events")
async def stream_events(
    rid: str,
    request: Request,
    after: int = 0,
    last_event_id: str | None = Header(default=None),
    user=Depends(current_user),
):
    db = request.app.state.db
    await db.get_run(user["id"], rid)
    try:
        cursor = max(0, int(last_event_id) if last_event_id is not None else after)
    except ValueError:
        raise HTTPException(400, "Invalid event cursor") from None

    async def generate():
        nonlocal cursor
        heartbeat = time.monotonic()
        while not await request.is_disconnected():
            rows = await db.events_after(rid, cursor)
            for row in rows:
                cursor = row["seq"]
                yield f"id: {cursor}\nevent: {row['kind']}\ndata: {json.dumps(row['data'])}\n\n"
                if row["kind"] == "finished":
                    return
            if not rows:
                run = await db.get_run(user["id"], rid)
                if run["status"] in TERMINAL and cursor >= run["event_seq"]:
                    return
            if time.monotonic() - heartbeat >= 10:
                yield ": heartbeat\n\n"
                heartbeat = time.monotonic()
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{cid}/download")
async def download(cid: str, request: Request, user=Depends(current_user)):
    conv = await request.app.state.db.conversation(user["id"], cid)
    parts = [f"# {conv['title']}\n"]
    for message in conv["messages"]:
        parts += [f"## {message['role'].title()}\n", message["content"]]
        result = message.get("result") or {}
        if result.get("notice"):
            parts.append(f"\nStatus: {result['notice']}")
        for source in result.get("sources", []):
            parts.append(
                f"\n[{source['id']}] {source['title']} — {source.get('url') or 'Uploaded document'}"
            )
        for claim in result.get("evidence", {}).get("claims", []):
            parts.append(
                f"\n- {claim['status']}: {claim['claim']}\n  Evidence: {claim.get('excerpt', '')}"
            )
    return Response(
        "\n\n".join(parts),
        media_type="text/markdown",
        headers={
            "Content-Disposition": 'attachment; filename="convene-conversation.md"'
        },
    )


@router.post("/files/parse")
async def parse_files(
    request: Request, files: list[UploadFile] = File(...), user=Depends(current_user)
):
    if len(files) > 3:
        raise HTTPException(422, "Attach at most three files")
    output = []
    allowed = {".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".py", ".js", ".ts"}
    for upload in files:
        try:
            name = (upload.filename or "document")[:200]
            if Path(name).suffix.lower() not in allowed:
                raise HTTPException(
                    422, "Use a text, Markdown, PDF, DOCX, CSV, JSON or source file"
                )
            content = await upload.read(5 * 1024 * 1024 + 1)
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(413, "Each document must be smaller than 5 MB")
            if Path(name).suffix.lower() == ".docx":
                try:
                    with ZipFile(io.BytesIO(content)) as z:
                        if sum(i.file_size for i in z.infolist()) > 20 * 1024 * 1024:
                            raise HTTPException(
                                413, "The expanded document is too large"
                            )
                except BadZipFile:
                    raise HTTPException(
                        422, "The document is not a valid DOCX file"
                    ) from None
            async with request.app.state.parse_limit:
                parsed = await asyncio.to_thread(
                    parse_document, content, name, upload.content_type or ""
                )
            if not parsed.text.strip():
                raise HTTPException(
                    422, "No text found. Scanned PDFs need OCR before upload."
                )
            output.append(
                {
                    "name": name,
                    "text": parsed.text[:24000],
                    "truncated": len(parsed.text) > 24000,
                }
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "The document could not be read") from None
        finally:
            await upload.close()
    return {"files": output}
