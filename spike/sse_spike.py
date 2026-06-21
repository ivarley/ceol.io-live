#!/usr/bin/env python3
"""
THROWAWAY SPIKE for spec 024 Phase 0 — validate the streaming triangle:

    POST /log  -->  (one txn) INSERT spike_event + pg_notify(channel, event_id)
                          |
                    Postgres LISTEN/NOTIFY
                          |
    GET /events (SSE) <-- LISTEN, re-read row by id, push `id: <event_id>` frame
                          |
            two browser tabs see the tune appear live

Run:  venv/bin/python spike/sse_spike.py   then open http://localhost:8030 in 2 tabs.
This is NOT the real service (real one is async Starlette+asyncpg). It only proves
LISTEN/NOTIFY -> SSE fan-out works end-to-end against the real Postgres.
"""
import json, select, threading, http.server, socketserver
import psycopg2

DSN = "host=localhost dbname=ceol_test"
CHAN = "spike_chan"
PORT = 8030

def db():
    return psycopg2.connect(DSN)

def setup():
    c = db(); c.autocommit = True
    c.cursor().execute("""
        CREATE TABLE IF NOT EXISTS spike_event (
            event_id BIGSERIAL PRIMARY KEY,
            payload  JSONB NOT NULL,
            server_ts TIMESTAMPTZ NOT NULL DEFAULT now()
        )""")
    c.close()

PAGE = """<!doctype html><meta charset=utf-8><title>SSE spike</title>
<style>body{font:16px system-ui;background:#0e0e10;color:#eee;margin:0;padding:16px}
input,button{font:16px system-ui;padding:8px}#log>div{padding:6px 8px;border-bottom:1px solid #333}
small{color:#888}</style>
<h3>024 streaming spike <small id=who></small></h3>
<input id=t placeholder="tune name" autofocus> <button onclick=send()>Log tune</button>
<span id=stat style=color:#888> connecting…</span>
<div id=log></div>
<script>
const me = Math.random().toString(36).slice(2,6);
who.textContent = '(tab '+me+')';
const es = new EventSource('/events');
es.onopen = ()=> stat.textContent=' live';
es.onerror= ()=> stat.textContent=' disconnected';
es.onmessage = e => {
  const d = JSON.parse(e.data);
  const row = document.createElement('div');
  row.innerHTML = '#'+e.lastEventId+' <b>'+d.name+'</b> <small>by tab '+d.by+'</small>';
  log.prepend(row);
};
async function send(){
  const name=t.value.trim(); if(!name) return; t.value='';
  await fetch('/log',{method:'POST',body:JSON.stringify({name,by:me})});
}
t.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
</script>"""

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # quiet

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200); self.send_header("Content-Type","text/html")
            self.send_header("Content-Length",str(len(body))); self.end_headers()
            self.wfile.write(body); return
        if self.path == "/events":
            self.stream_events(); return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/log": return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        conn = db()  # one transaction: insert event + notify, atomically
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO spike_event(payload) VALUES (%s) RETURNING event_id",
                        (json.dumps(data),))
            event_id = cur.fetchone()[0]
            cur.execute("SELECT pg_notify(%s, %s)", (CHAN, str(event_id)))
            conn.commit()
        finally:
            conn.close()
        self.send_response(204); self.end_headers()

    def stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type","text/event-stream")
        self.send_header("Cache-Control","no-cache")
        self.send_header("Connection","keep-alive")
        self.end_headers()
        conn = db(); conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"LISTEN {CHAN}")
        try:
            while True:
                # wait up to 15s for a NOTIFY; otherwise send a keepalive comment
                if select.select([conn], [], [], 15) == ([], [], []):
                    self.wfile.write(b": ping\n\n"); self.wfile.flush(); continue
                conn.poll()
                while conn.notifies:
                    note = conn.notifies.pop(0)
                    event_id = int(note.payload)
                    # NOTIFY carried only the id -> re-read the row (the real pattern)
                    cur.execute("SELECT payload FROM spike_event WHERE event_id=%s",(event_id,))
                    payload = cur.fetchone()[0]
                    frame = f"id: {event_id}\ndata: {json.dumps(payload)}\n\n"
                    self.wfile.write(frame.encode()); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client tab closed
        finally:
            conn.close()

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    setup()
    print(f"spike up: http://localhost:{PORT}  (open 2 tabs)")
    Server(("0.0.0.0", PORT), H).serve_forever()
