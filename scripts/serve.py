#!/usr/bin/env python3
"""Range-capable static file server for local PMTiles preview.

`python -m http.server` does not honour HTTP Range requests, which PMTiles' MapLibre
protocol relies on (byte-range reads). This minimal server returns 206 Partial Content.

Usage:  python scripts/serve.py [port] [dir]   (defaults: 8080  dist)
"""
import os
import re
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()
        m = RANGE_RE.match(rng)
        if not m:
            return super().send_head()
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else 0
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416, "Requested Range Not Satisfiable")
            return None
        length = end - start + 1
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self._remaining = length
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    directory = sys.argv[2] if len(sys.argv) > 2 else "dist"
    handler = partial(RangeHandler, directory=directory)
    print(f"serving {directory}/ on http://localhost:{port}  (Range-capable)")
    HTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
