"""Transport-only test producer. It is never registered as an application endpoint."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"services/backend"))

from app import db
from app.events import emit, text_delta


async def main():
    owner,conversation,bot=sys.argv[1:]
    await db.open_pool()
    run_id=db.new_id()
    try:
        await db.execute("INSERT INTO runs(id,owner_id,bot_id,conversation_id,status,mode,question,request_key,request_hash,started_at) "
                         "VALUES(%s,%s,%s,%s,'RUNNING','EVIDENCE','SSE transport fixture',%s,'test-fixture',now())",
                         (run_id,owner,bot,conversation,db.new_id()))
        for role,text,status in [("user","Verify SSE page-leave recovery (test fixture).","COMPLETED"),("assistant","","RUNNING")]:
            await db.execute("INSERT INTO messages(id,owner_id,conversation_id,run_id,role,text,status) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                             (db.new_id(),owner,conversation,run_id,role,text,status))
        await db.execute("UPDATE conversations SET title='SSE recovery fixture' WHERE id=%s",(conversation,))
        print(json.dumps({"run_id":run_id}),flush=True)
        await emit(owner,run_id,"run.started",{})
        for index in range(1,7):
            await text_delta(owner,run_id,f"Part {index}. ")
            await asyncio.sleep(1)
        await db.execute("UPDATE messages SET status='COMPLETED' WHERE run_id=%s",(run_id,))
        await db.execute("UPDATE runs SET status='COMPLETED',finished_at=now() WHERE id=%s",(run_id,))
        await emit(owner,run_id,"run.completed",{})
    finally:
        await db.close_pool()


asyncio.run(main())
