import datetime
import http.server
import json
import os
import shutil
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# 保存を受け付けるのは、この1つだけ（ファイル名は固定）
SAVE_PATHS = {"/api/save-tasks": "tasks.json"}
MAX_BYTES = 5 * 1024 * 1024
KEEP_BACKUPS = 14


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _reply(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self):
        # 他のサイトからの書き込みを防ぐ（このアプリのアドレスからだけ許可）
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return origin in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

    def do_POST(self):
        name = SAVE_PATHS.get(self.path)
        if not name or not self._origin_ok():
            return self._reply(403, {"ok": False})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BYTES:
            return self._reply(413, {"ok": False})
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._reply(400, {"ok": False})
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
            return self._reply(400, {"ok": False})

        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            # 1日1回、保存の前の状態を backups フォルダに残す（最新14日分）
            bdir = os.path.join(ROOT, "backups")
            os.makedirs(bdir, exist_ok=True)
            b = os.path.join(bdir, "tasks-" + datetime.date.today().isoformat() + ".json")
            if not os.path.exists(b):
                shutil.copyfile(path, b)
            old = sorted(f for f in os.listdir(bdir) if f.startswith("tasks-"))
            for f in old[:-KEEP_BACKUPS]:
                os.remove(os.path.join(bdir, f))

        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        self._reply(200, {"ok": True})


http.server.ThreadingHTTPServer.allow_reuse_address = True
with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Taskmate: http://localhost:{PORT}  （このウィンドウを閉じると終了します）")
    httpd.serve_forever()
