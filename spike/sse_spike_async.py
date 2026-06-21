#!/usr/bin/env python3
"""
THROWAWAY SPIKE #2 for spec 024 Phase 0 — the REAL stack: Starlette + asyncpg.

Adds what spike #1 didn't cover:
  - the actual async runtime we chose (asyncpg LISTEN + Starlette SSE), proving
    held connections work under the event loop (not a thread per connection)
  - Last-Event-ID REPLAY then go-live (gap recovery / offline catch-up, §B)

Run:  venv/bin/python spike/sse_spike_async.py   then open http://localhost:8031
"""
import asyncio, json
from contextlib import asynccontextmanager
import asyncpg
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, Response, StreamingResponse
from starlette.routing import Route

DSN = "postgresql://localhost/ceol_test"
CHAN = "spike_chan"
PORT = 8031
pool: asyncpg.Pool = None

PAGE = """<!doctype html><meta charset=utf-8><title>SSE spike async</title>
<style>body{font:16px system-ui;background:#0e0e10;color:#eee;margin:0;padding:16px}
input,button{font:16px system-ui;padding:8px}#log>div{padding:6px 8px;border-bottom:1px solid #333}
small{color:#888}</style>
<h3>024 async spike <small id=who></small></h3>
<input id=t placeholder="tune name" autofocus> <button onclick=send()>Log tune</button>
<span id=stat style=color:#888> connecting…</span>
<div id=log></div>
<script>
const me = Math.random().toString(36).slice(2,6); who.textContent='(tab '+me+')';
const es = new EventSource('/events');          // EventSource auto-sends Last-Event-ID on reconnect
es.onopen=()=>stat.textContent=' live'; es.onerror=()=>stat.textContent=' reconnecting…';
es.onmessage=e=>{const d=JSON.parse(e.data);const r=document.createElement('div');
  r.innerHTML='#'+e.lastEventId+' <b>'+d.name+'</b> <small>by tab '+d.by+'</small>';log.prepend(r);};
async function send(){const name=t.value.trim();if(!name)return;t.value='';
  await fetch('/log',{method:'POST',body:JSON.stringify({name,by:me})});}
t.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
</script>"""

async def home(req):
    return HTMLResponse(PAGE)

async def log_tune(req):
    data = json.loads(await req.body() or b"{}")
    async with pool.acquire() as conn:           # one transaction: insert + notify
        async with conn.transaction():
            eid = await conn.fetchval(
                "INSERT INTO spike_event(payload) VALUES ($1) RETURNING event_id",
                json.dumps(data))
            await conn.execute("SELECT pg_notify($1,$2)", CHAN, str(eid))
    return Response(status_code=204)

async def events(req):
    last = int(req.headers.get("last-event-id", 0))   # gap recovery cursor

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()
        listen_conn = await pool.acquire()
        def on_notify(c, pid, chan, payload):         # asyncpg callback -> queue
            queue.put_nowait(int(payload))
        await listen_conn.add_listener(CHAN, on_notify)
        try:
            # 1) REPLAY everything after the client's cursor, note the high-water mark
            rows = await listen_conn.fetch(
                "SELECT event_id, payload FROM spike_event WHERE event_id > $1 ORDER BY event_id",
                last)
            replayed_through = last
            for r in rows:
                replayed_through = r["event_id"]
                yield f"id: {r['event_id']}\ndata: {r['payload']}\n\n".encode()
            # 2) GO LIVE — drain queued notifies, skipping any already covered by replay
            while True:
                try:
                    eid = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield b": ping\n\n"; continue
                if eid <= replayed_through:
                    continue                          # dedupe replay/live overlap
                payload = await listen_conn.fetchval(
                    "SELECT payload FROM spike_event WHERE event_id=$1", eid)
                yield f"id: {eid}\ndata: {payload}\n\n".encode()
                if await req.is_disconnected():
                    break
        finally:
            await listen_conn.remove_listener(CHAN, on_notify)
            await pool.release(listen_conn)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})

@asynccontextmanager
async def lifespan(app):
    global pool
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=10)
    async with pool.acquire() as c:
        await c.execute("""CREATE TABLE IF NOT EXISTS spike_event(
            event_id BIGSERIAL PRIMARY KEY, payload JSONB NOT NULL,
            server_ts TIMESTAMPTZ NOT NULL DEFAULT now())""")
    print(f"async spike up: http://localhost:{PORT}")
    yield
    await pool.close()

app = Starlette(routes=[Route("/", home), Route("/log", log_tune, methods=["POST"]),
                        Route("/events", events)], lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
