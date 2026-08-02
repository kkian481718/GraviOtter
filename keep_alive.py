from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"GraviOtter is awake and swimming!")
        
    def log_message(self, format, *args):
        pass # 不要瘋狂印出存取紀錄，保持終端機乾淨

def run():
    server = HTTPServer(('0.0.0.0', 8080), RequestHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
