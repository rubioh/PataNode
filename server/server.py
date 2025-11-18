import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time


class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/get_graphs":
            self.get_graphs()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Available routes are: /get_graphs")

    def get_graphs(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        # print(type(), self.server.graphs_data)
        json_data = self.server.graphs_data
        #        json_data = json.loads(json_data)
        self.wfile.write(json.dumps(json_data).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        response = b"Received POST: " + post_data
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(response)


class PataServer:
    def __init__(self, args, app, host="localhost", port=4242):
        #        with open("./server/example.json") as f:
        #            self.example = json.load(f)
        # self.server.example = self.example
        self.app = app
        self.server = HTTPServer((host, port), SimpleHandler)
        self.server.graphs_data = {}
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True  # Allows program to exit even if thread is running

    def update(self):
        self.server.graphs_data = self.app.poll_graphs()
        time.sleep(1.0 / 60.0)
        pass

    def start(self):
        print("Starting http server...")
        self.thread.start()

    def stop(self):
        print("Stopping http server...")
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
