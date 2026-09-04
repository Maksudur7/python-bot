import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import database
from automation_bot import SMSBowerBot

PORT = 8000
bot_instance = SMSBowerBot()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class DashboardRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard HTTP request logging in terminal
        pass

    def _send_json(self, data, status_code=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath, content_type='text/html', as_attachment=False, filename=None):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        
        with open(filepath, 'rb') as f:
            content = f.read()

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        if as_attachment and filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/" or path == "/index.html":
            tmpl_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            self._send_file(tmpl_path, "text/html; charset=utf-8")
        
        elif path == "/static/style.css":
            css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
            self._send_file(css_path, "text/css; charset=utf-8")

        elif path == "/static/app.js":
            js_path = os.path.join(os.path.dirname(__file__), "static", "app.js")
            self._send_file(js_path, "application/javascript; charset=utf-8")

        elif path == "/api/state":
            records = database.get_all_records()
            state_data = {
                "is_running": bot_instance.is_running,
                "metrics": {
                    "numbers_checked": bot_instance.numbers_checked,
                    "records_saved": bot_instance.records_saved,
                    "cancelled_cost": bot_instance.cancelled_cost,
                    "current_status": bot_instance.current_status
                },
                "logs": bot_instance.logs,
                "records": records
            }
            self._send_json(state_data)

        elif path == "/api/bot/export_csv":
            csv_path = os.path.join(os.path.dirname(__file__), "saved_numbers_sheet.csv")
            self._send_file(csv_path, "text/csv", as_attachment=True, filename="saved_numbers_sheet.csv")

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            body_data = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            body_data = {}

        if path == "/api/bot/start":
            headless = body_data.get("headless", False)
            del bot_instance.logs[:]
            success = bot_instance.start(headless=headless)
            if success:
                self._send_json({"status": "ok", "message": "Bot engine started"})
            else:
                self._send_json({"status": "error", "message": "Bot is already running"}, status_code=400)

        elif path == "/api/bot/stop":
            success = bot_instance.stop()
            bot_instance.logs.clear()
            if success:
                self._send_json({"status": "ok", "message": "Bot stopping"})
            else:
                self._send_json({"status": "error", "message": "Bot is not running"}, status_code=400)

        elif path == "/api/bot/record":
            if bot_instance.is_running:
                bot_instance.stop()
            
            import subprocess, sys
            venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
            if not os.path.exists(venv_python):
                venv_python = sys.executable
            
            rec_script = os.path.join(os.path.dirname(__file__), "record_workflow.py")
            subprocess.Popen([venv_python, rec_script])
            self._send_json({"status": "ok", "message": "Playwright Workflow Recorder launched!"})

        else:
            self.send_error(404, "Endpoint not found")

def main():
    database.init_db()
    bot_instance.logs.clear()
    print("============================================================")
    print("SMSBower Cabinet & FamilyTreeNow Automation Dashboard")
    print(f"Local Server running at: http://localhost:{PORT}")
    print("============================================================")
    
    server = ThreadedHTTPServer(('0.0.0.0', PORT), DashboardRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        bot_instance.stop()
        server.server_close()

if __name__ == "__main__":
    main()
