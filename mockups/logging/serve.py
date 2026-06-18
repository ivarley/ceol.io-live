#!/usr/bin/env python3
"""Static server with hard no-cache headers, so prototype edits always reach the phone."""
import http.server
import socketserver

PORT = 8021


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), NoCacheHandler) as httpd:
    print(f"serving (no-cache) on 0.0.0.0:{PORT}")
    httpd.serve_forever()
