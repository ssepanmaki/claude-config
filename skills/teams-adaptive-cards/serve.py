"""Serve a folder on 127.0.0.1 so the hosted Adaptive Card Designer page can fetch cards and render.mjs."""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class _Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".json": "application/json"}

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "https://adaptivecards.microsoft.com")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()


def main() -> None:
    root, port = sys.argv[1], int(sys.argv[2])
    ThreadingHTTPServer(("127.0.0.1", port), partial(_Handler, directory=root)).serve_forever()


if __name__ == "__main__":
    main()
