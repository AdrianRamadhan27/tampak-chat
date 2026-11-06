"""Database-leased jobs. Browser disconnects never own or cancel these tasks."""

import asyncio
import logging
import shutil
import signal
import sys
import time
from uuid import UUID

from app import db
from app.chat import CancelledRun, execute_run
from app.errors import AppError
from app.evaluation import execute_evaluation, interrupt_answers, persist
from app.events import emit
from app.ingestion import index_revision, process_revision, storage_path

logger = logging.getLogger("tampak.worker")


async def claim(kind: str) -> dict | None:
    async with db.connection() as conn:
        cursor = await conn.execute(
            "WITH next AS (SELECT id FROM jobs WHERE kind=ANY(%s::text[]) AND status='QUEUED' AND available_at<=now() "
            "ORDER BY CASE WHEN kind='chat' THEN 0 ELSE 1 END,created_at FOR UPDATE SKIP LOCKED LIMIT 1) "
            "UPDATE jobs j SET status='RUNNING',attempts=attempts+1,lease_token=%s,"
            "lease_until=now()+interval '45 seconds',heartbeat_at=now() FROM next WHERE j.id=next.id RETURNING j.*",
            (["chat", "evaluation"] if kind == "chat" else [kind], db.new_id()),
        )
        return await cursor.fetchone()


async def heartbeat(job: dict) -> None:
    while True:
        await asyncio.sleep(10)
        changed = await db.execute(
            "UPDATE jobs SET lease_until=now()+interval '45 seconds',heartbeat_at=now() "
            "WHERE id=%s AND lease_token=%s AND status='RUNNING'",
            (job["id"], job["lease_token"]),
        )
        if not changed:
            raise CancelledRun()


async def cancellation(job: dict) -> None:
    while True:
        await asyncio.sleep(0.4)
        principal = await db.one(
            "SELECT expires_at FROM principals WHERE id=%s", (job["owner_id"],)
        )
        if not principal or principal["expires_at"] and principal["expires_at"] < db.now():
            return
        if job["kind"] == "evaluation":
            evaluation = await db.one(
                "SELECT cancel_requested,status FROM evaluation_runs WHERE id=%s",
                (job["target_id"],),
            )
            if (
                not evaluation
                or evaluation["cancel_requested"]
                or evaluation["status"] in {"CANCELLED", "INTERRUPTED"}
            ):
                return
        elif job["kind"] == "chat":
            run = await db.one(
                "SELECT cancel_requested,status FROM runs WHERE id=%s", (job["target_id"],)
            )
            if not run or run["cancel_requested"] or run["status"] in {"CANCELLED", "INTERRUPTED"}:
                return
        else:
            source = await db.one(
                "SELECT s.deleted_at FROM source_revisions r JOIN sources s ON s.id=r.source_id WHERE r.id=%s",
                (job["target_id"],),
            )
            if not source or source["deleted_at"]:
                return
        bot = await db.one("SELECT deleted_at,expires_at FROM bots WHERE id=%s", (job["bot_id"],))
        if not bot or bot["deleted_at"] or bot["expires_at"] and bot["expires_at"] < db.now():
            return


async def fail(job: dict, status: str, error: dict) -> None:
    target, owner = str(job["target_id"]), str(job["owner_id"])
    if job["kind"] == "evaluation":
        await interrupt_answers(target, status, error)
        batch = await db.one("SELECT * FROM evaluation_runs WHERE id=%s", (target,))
        if batch:
            for case in batch["cases"]:
                if case["status"] not in {"COMPLETED", "PARTIAL", "FAILED"}:
                    case["status"] = "SKIPPED" if case["status"] == "QUEUED" else status
            await persist(batch)
        await db.execute(
            "UPDATE evaluation_runs SET status=%s,error=%s,finished_at=now() WHERE id=%s AND status IN ('QUEUED','RUNNING')",
            (status, db.jsonb(error), target),
        )
        await emit(owner, target, "evaluation.ended", {"status": status, "error": error})
    elif job["kind"] == "chat":
        async with db.connection() as conn:
            await conn.execute(
                "UPDATE runs SET status=%s,error=%s,finished_at=now() WHERE id=%s AND status IN ('QUEUED','RUNNING')",
                (status, db.jsonb(error), target),
            )
            await conn.execute(
                "UPDATE messages SET status=%s WHERE run_id=%s AND role='assistant' AND status!='COMPLETED'",
                (status, target),
            )
        await emit(owner, target, "run.ended", {"status": status, "error": error})
    else:
        await db.execute(
            "UPDATE source_revisions SET status='FAILED',error=%s WHERE id=%s",
            (db.jsonb(error), target),
        )
        await emit(owner, target, "ingestion.failed", {"error": error})
    await db.execute(
        "UPDATE jobs SET status=%s,error=%s,finished_at=now() WHERE id=%s AND lease_token=%s",
        (status, db.jsonb(error), job["id"], job["lease_token"]),
    )


async def recover_expired() -> None:
    # Never automatically repeat an uncertain, potentially billed provider call.
    rows = await db.many(
        "UPDATE jobs SET status='INTERRUPTED' WHERE status='RUNNING' AND lease_until<now() RETURNING *"
    )
    for job in rows:
        async with db.connection() as conn:
            await conn.execute(
                "UPDATE provider_calls SET status='INTERRUPTED',finished_at=now() "
                "WHERE stream_id=%s AND status='STARTED'",
                (job["target_id"],),
            )
            await conn.execute(
                "UPDATE budget_reservations SET status='UNCERTAIN' WHERE id IN "
                "(SELECT id FROM provider_calls WHERE stream_id=%s AND status='INTERRUPTED')",
                (job["target_id"],),
            )
        await fail(
            job,
            "INTERRUPTED",
            {
                "code": "WORKER_INTERRUPTED",
                "message": "The worker stopped before the run completed. Partial output is preserved. Retry explicitly; the prior attempt may have been billed.",
            },
        )


async def run_job(job: dict) -> None:
    task = asyncio.create_task(
        execute_evaluation(str(job["target_id"]))
        if job["kind"] == "evaluation"
        else execute_run(str(job["target_id"]))
        if job["kind"] == "chat"
        else index_revision(str(job["target_id"]))
        if job["payload"].get("step") == "index"
        else process_revision(str(job["target_id"]))
    )
    pulse = asyncio.create_task(heartbeat(job))
    cancel = asyncio.create_task(cancellation(job))
    try:
        done, _ = await asyncio.wait({task, pulse, cancel}, return_when=asyncio.FIRST_COMPLETED)
        if pulse in done or cancel in done:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise CancelledRun()
        await task
        await db.execute(
            "UPDATE jobs SET status='COMPLETED',finished_at=now() WHERE id=%s AND lease_token=%s AND status='RUNNING'",
            (job["id"], job["lease_token"]),
        )
    except CancelledRun:
        await fail(
            job,
            "CANCELLED",
            {"code": "CANCELLED", "message": "This run was stopped. Partial output is preserved."},
        )
    except AppError as error:
        await fail(job, "FAILED", {"code": error.code, "message": error.message})
    except Exception:
        logger.exception("Job %s failed", job["id"])
        await fail(
            job,
            "FAILED",
            {
                "code": "JOB_FAILED",
                "message": "The job failed. Check the worker log and retry explicitly.",
            },
        )
    finally:
        pulse.cancel()
        cancel.cancel()
        await asyncio.gather(pulse, cancel, return_exceptions=True)


async def cleanup() -> None:
    expired = await db.many("SELECT id FROM principals WHERE kind='GUEST' AND expires_at<now()")
    for principal in expired:
        owner = principal["id"]
        active = await db.one(
            "SELECT count(*) AS n FROM jobs WHERE owner_id=%s AND status='RUNNING'", (owner,)
        )
        if active["n"]:
            await db.execute(
                "UPDATE runs SET cancel_requested=true WHERE owner_id=%s AND status IN ('QUEUED','RUNNING')",
                (owner,),
            )
            continue
        keys = await db.many("SELECT storage_key FROM source_revisions WHERE owner_id=%s", (owner,))
        async with db.connection() as conn:
            # Revoke access before removing all dependent material.
            await conn.execute("DELETE FROM sessions WHERE principal_id=%s", (owner,))
            for table in [
                "events",
                "budget_reservations",
                "provider_calls",
                "visualizations",
                "analysis_results",
                "jobs",
                "messages",
                "runs",
                "datasets",
                "chunks",
            ]:
                await conn.execute(f"DELETE FROM {table} WHERE owner_id=%s", (owner,))
            await conn.execute(
                "UPDATE sources SET active_revision_id=NULL WHERE owner_id=%s", (owner,)
            )
            await conn.execute("DELETE FROM source_revisions WHERE owner_id=%s", (owner,))
            await conn.execute("DELETE FROM sources WHERE owner_id=%s", (owner,))
            await conn.execute("DELETE FROM conversations WHERE owner_id=%s", (owner,))
            await conn.execute("DELETE FROM bots WHERE owner_id=%s", (owner,))
            await conn.execute("DELETE FROM principals WHERE id=%s", (owner,))
        for key in keys:
            shutil.rmtree(storage_path(key["storage_key"]).parent, ignore_errors=True)
    # Retry artifact deletion after a crash between committing database cleanup and unlinking files.
    known = {str(row["id"]) for row in await db.many("SELECT id FROM source_revisions")}
    source_root = storage_path("sources")
    if source_root.exists():
        for folder in source_root.iterdir():
            try:
                UUID(folder.name)
                if (
                    folder.is_dir()
                    and folder.name not in known
                    and time.time() - folder.stat().st_mtime > 300
                ):
                    shutil.rmtree(folder, ignore_errors=True)
            except (ValueError, FileNotFoundError):
                continue


async def loop(kind: str, stop: asyncio.Event, maintenance: bool = False) -> None:
    cycles = 0
    while not stop.is_set():
        try:
            if maintenance and cycles % 30 == 0:
                await recover_expired()
                await cleanup()
            job = await claim(kind)
            if job:
                await run_job(job)
            else:
                try:
                    await asyncio.wait_for(stop.wait(), 1)
                except TimeoutError:
                    pass
            cycles += 1
        except Exception:
            logger.exception("Worker poll failed")
            await asyncio.sleep(3)


async def main(kind: str) -> None:
    await db.open_pool()
    stop = asyncio.Event()
    loop_ = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop_.add_signal_handler(sig, stop.set)
    count = 2 if kind == "chat" else 1
    try:
        await asyncio.gather(*(loop(kind, stop, i == 0) for i in range(count)))
    finally:
        await db.close_pool()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "chat"))
