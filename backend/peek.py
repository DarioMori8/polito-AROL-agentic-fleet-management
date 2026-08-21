import asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

DB = "data/checkpoints.sqlite"   # DEVE essere lo stesso valore di CHECKPOINT_DB_PATH

async def main():
    async with AsyncSqliteSaver.from_conn_string(DB) as saver:
        seen = set()
        async for cp in saver.alist(None):        # None = nessun filtro, tutti i checkpoint
            tid = cp.config["configurable"]["thread_id"]
            if tid not in seen:
                seen.add(tid)
                print("thread_id:", tid)
        if not seen:
            print(">>> lo store è VUOTO: nessun checkpoint salvato affatto")

asyncio.run(main())