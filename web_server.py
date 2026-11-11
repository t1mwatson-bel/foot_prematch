import os
import http.server
import socketserver

from config import STATS_HTML_FILE


def start_web_server():
    port = int(os.getenv("PORT", 8000))

    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass

    class StatsHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Анти-кэш: браузер всегда берёт свежий stats.html
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def do_GET(self):
            if self.path in ("/", "/health"):
                if os.path.exists(STATS_HTML_FILE):
                    self.path = "/" + STATS_HTML_FILE
                    return super().do_GET()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("OK".encode("utf-8"))
                return
            return super().do_GET()

        def log_message(self, format, *args):
            pass

    try:
        with socketserver.TCPServer(("0.0.0.0", port), StatsHandler) as httpd:
            print(f"🌐 Веб-сервер запущен: 0.0.0.0:{port}", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"⚠️ Ошибка веб-сервера на порту {port}: {e}", flush=True)