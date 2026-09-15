import asyncio
from backend.config import config
from backend.storage.database import StoreError
from backend.core.orchestrator import Orchestrator
from backend.llm.gateway import BudgetExceeded, ProviderFailure


class RunService:
    def __init__(self, db, gateway, evidence):
        self.db, self.gateway, self.evidence = db, gateway, evidence
        self.tasks = {}
        self.submissions = asyncio.Lock()
        self.slots = asyncio.Semaphore(config.MAX_ACTIVE_RUNS)
        self.shutting_down = False

    async def submit(self, owner, conversation_id, request):
        # Serialize queue admission in the supported single-process deployment.
        async with self.submissions:
            if len(self.tasks) >= config.MAX_ACTIVE_RUNS * 4:
                existing = await self.db.run_for_request(owner, request["request_key"])
                if not existing:
                    raise StoreError(
                        "The queue is full. Please try again shortly.", 429
                    )
            run, created = await self.db.create_run(
                owner, conversation_id, request, config.DAILY_RUN_LIMIT
            )
            if created:
                self.start(run)
            return run

    def start(self, run):
        task = asyncio.create_task(self.execute(run), name=f"convene-{run['id']}")
        self.tasks[run["id"]] = task
        task.add_done_callback(lambda done: self.tasks.pop(run["id"], None))
        # Retrieve unexpected exceptions; no unobserved task errors or secret tracebacks.
        task.add_done_callback(
            lambda done: None if done.cancelled() else done.exception()
        )

    async def persist(self, operation):
        # Finish transaction cleanup before cancellation starts another write.
        task = asyncio.create_task(operation)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    async def execute(self, run):
        rid = run["id"]

        async def emit(kind, data):
            await self.persist(self.db.emit(rid, kind, data))

        async def checkpoint(result):
            await self.persist(self.db.checkpoint(rid, result))

        agent = Orchestrator(self.gateway, self.evidence, emit, checkpoint)
        agent.result["run_id"] = rid
        try:
            await emit("queued", {"message": "Your question is queued"})
            # Queue time is included in the deadline; abandoned requests cannot wait forever.
            async with asyncio.timeout(config.COMPLEX_REQUEST_TIMEOUT):
                async with self.slots:
                    conv = await self.db.conversation(
                        run["owner_id"], run["conversation_id"]
                    )
                    request = dict(run["request"])
                    if not request.get("documents"):
                        request["documents"] = await self.db.recent_documents(
                            run["owner_id"], run["conversation_id"]
                        )
                    result = await agent.run(request, conv["messages"][:-1])
            await self.persist(self.db.finish(rid, result["status"], result))
        except asyncio.CancelledError:
            state = "interrupted" if self.shutting_down else "cancelled"
            result = agent.partial(
                "The server stopped. Saved progress is retained."
                if self.shutting_down
                else "You stopped this answer.",
                state,
            )
            await self.persist(self.db.finish(rid, state, result))
        except (TimeoutError, BudgetExceeded, ProviderFailure) as e:
            note = (
                "The question reached its time limit."
                if isinstance(e, TimeoutError)
                else str(e)
            )
            result = agent.partial(note)
            state = "partial" if result.get("content") else "failed"
            result["status"] = state
            await self.persist(self.db.finish(rid, state, result))
        except Exception:
            result = agent.partial(
                "The run could not finish. Saved progress is available."
            )
            state = "partial" if result.get("content") else "failed"
            result["status"] = state
            await self.persist(self.db.finish(rid, state, result))

    async def cancel(self, owner, rid):
        run = await self.db.get_run(owner, rid)
        task = self.tasks.get(rid)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        run = await self.db.get_run(owner, rid)
        if run["status"] in ("queued", "running"):
            await self.db.finish(
                rid,
                "cancelled",
                {
                    "status": "cancelled",
                    "content": "",
                    "notice": "You stopped this answer.",
                },
            )

    async def close(self):
        self.shutting_down = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
