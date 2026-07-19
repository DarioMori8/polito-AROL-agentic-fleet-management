import asyncio
from app.clients.manuals_client import ManualsClient

async def main():
    client = ManualsClient()
    result = await client.search(query="perché la macchina non funziona?", machine_id="2")
    print(result)

asyncio.run(main())