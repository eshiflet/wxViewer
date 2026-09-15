#!/usr/bin/env python3
"""Minimal static file server with /api/files JSON endpoint."""
import json, os
from http.server import SimpleHTTPRequestHandler, HTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIR, **kw)

    def do_GET(self):
        if self.path == '/api/files':
            files = sorted(f for f in os.listdir(DIR) if f.lower().endswith('.csv'))
            body = json.dumps(files).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, fmt, *args):
        pass  # silence

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5201
    print(f'Serving {DIR} on http://localhost:{port}')
    HTTPServer(('', port), Handler).serve_forever()
