pass
import functools, os, socket, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import mpaths


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server:
    def __init__(self, root=mpaths.SRC_MAPS):
        self.root = root

    def __enter__(self):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]; s.close()
        h = functools.partial(_Quiet, directory=self.root)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), h)
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()
        return self

    def url(self, p):
        rel = os.path.relpath(os.path.abspath(p), self.root).replace(os.sep, "/")
        assert not rel.startswith(".."), p
        from urllib.parse import quote
        return f"http://127.0.0.1:{self.port}/{quote(rel)}"

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
