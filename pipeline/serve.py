"""Serve site/ locally, with the HTTP range requests that PMTiles needs.

Usage:
    uv run python pipeline/serve.py          # http://localhost:8000
    uv run python pipeline/serve.py 8080     # another port

A range request asks for one slice of a file ("bytes=0-999"), so the browser can read a few
map tiles out of a large file. Python's built-in http.server always sends the whole file.
This is for local development only; GitHub Pages does the serving once the site is deployed.
"""

import argparse
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class RangeHandler(SimpleHTTPRequestHandler):
    range_length = None  # how many bytes to send; None means the whole file

    def end_headers(self):
        # Make the browser check for a newer file each time, so edits show up on reload.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not match or match.groups() == ("", "") or not os.path.isfile(path):
            return super().send_head()

        size = os.path.getsize(path)
        first, last = match.groups()
        if first:  # "bytes=100-199", or "bytes=100-" for everything from 100 on
            start, end = int(first), min(int(last), size - 1) if last else size - 1
        else:  # "bytes=-500" means the last 500 bytes
            start, end = max(size - int(last), 0), size - 1
        if start >= size or start > end:
            self.send_error(416, "Requested range not satisfiable")
            return None

        source = open(path, "rb")
        source.seek(start)
        self.range_length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self.range_length))
        self.end_headers()
        return source

    def copyfile(self, source, outputfile):
        try:
            if self.range_length is None:
                super().copyfile(source, outputfile)
            else:
                outputfile.write(source.read(self.range_length))
        except ConnectionError:
            pass  # the browser stopped waiting, as it does for tiles you pan or zoom away from

    def log_request(self, code="-", size="-"):
        if code != 206:  # tile requests come by the hundreds; log everything else
            super().log_request(code, size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("port", nargs="?", type=int, default=8000)
    port = parser.parse_args().port
    handler = partial(RangeHandler, directory=str(SITE))
    print(f"Serving {SITE} at http://localhost:{port} (Ctrl+C to stop)")
    try:
        ThreadingHTTPServer(("", port), handler).serve_forever()
    except KeyboardInterrupt:
        print("Stopped")


if __name__ == "__main__":
    main()
