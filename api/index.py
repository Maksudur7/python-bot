import os
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler

# Ensure parent directory is in Python path for database module
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import database

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        base_dir = os.path.dirname(os.path.dirname(__file__))

        if path == "/" or path == "/index.html":
            tmpl_path = os.path.join(base_dir, "templates", "index.html")
            self._send_file(tmpl_path, "text/html; charset=utf-8")
        
        elif path == "/static/style.css":
            css_path = os.path.join(base_dir, "static", "style.css")
            self._send_file(css_path, "text/css; charset=utf-8")

        elif path == "/static/app.js":
            js_path = os.path.join(base_dir, "static", "app.js")
            self._send_file(js_path, "application/javascript; charset=utf-8")

        elif path == "/api/state":
            database.init_db()
            records = database.get_all_records()
            state_data = {
                "is_running": False,
                "metrics": {
                    "numbers_checked": 0,
                    "records_saved": len(records),
                    "cancelled_cost": 0,
                    "current_status": "CLOUD_IDLE"
                },
                "logs": ["[System] Vercel Cloud Dashboard live."],
                "records": records
            }
            self._send_json(state_data)

        elif path == "/api/bot/export_csv":
            csv_path = os.path.join(base_dir, "saved_numbers_sheet.csv")
            self._send_file(csv_path, "text/csv", as_attachment=True, filename="saved_numbers_sheet.csv")

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/bot/start":
            self._send_json({
                "status": "ok",
                "message": "Vercel Cloud UI Active. Note: Automation bot runs on your local machine."
            })
        elif path == "/api/bot/stop":
            self._send_json({"status": "ok", "message": "Bot engine stopped"})
        else:
            self.send_error(404, "Endpoint not found")

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
