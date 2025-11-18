import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Hello from the server!")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b''
        response = b"Received POST: " + post_data

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(response)

class PataServer:
    def __init__(self, args, host='localhost', port=4242):
        self.server = HTTPServer((host, port), SimpleHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True  # Allows program to exit even if thread is running

    def start(self):
        print("Starting http server...")
        self.thread.start()

    def stop(self):
        print("Stopping http server...")
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()