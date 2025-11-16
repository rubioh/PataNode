import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time


class SimpleHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if "/get_image/" in self.path:
            return self.get_image(self.path[len("/get_image/"):])
        elif self.path == "/get_graphs":
            self.get_graphs()
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Available routes are: /get_graphs")

    def get_image(self, name):
        img  = self.server.app.previews[name][1]
        self.send_response(200)
        self.send_header('Content-type', 'image/bmp')
        self.send_header('Connection', 'keep-alive')
        self.send_header("Content-Length", str(len(img)))
        self.end_headers()
        # Send the BMP data
        self.wfile.write(img)

    def get_graphs(self):
        json_data = self.server.graphs_data
        #        json_data = json.loads(json_data)
        ret = json.dumps(json_data).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header('Connection', 'keep-alive')
        self.send_header("Content-Length", str(len(ret)))
        self.end_headers()
        self.server.graphs_data = self.server.app.poll_graphs()
        self.wfile.write(ret)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        response = b"Received POST: " + post_data
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(response)
        if "/update_mapping" in self.path:
            path = self.path[len("/update_mapping?wireframe="):]
            args = path.split("&")
            args = args[:-1]
            wireframe = False
            if args.pop(0) == "true":
                wireframe = True
            num_poly = len(args)
            polygons = []
            poly_idx = 0
            while num_poly > 0:
                poly = args.pop(0).split(";")
                polygons.append([])
                while len(poly):
                    while len(poly):
                        point = poly.pop(0).split(",")
                        if point != ['']:
                            polygons[poly_idx].append(float(point[0]))
                            polygons[poly_idx].append(float(point[1]))
                poly_idx += 1

                num_poly = num_poly - 1
            self.server.app.update_global_mapping(wireframe, polygons)
            return
        if "/set_active_graph" in self.path:
            path = self.path[len("/set_active_graph?graph="):]
            self.server.app.set_active_graph(path)
            return
        if "/change_parameter" in self.path:
            path = self.path[len("/change_parameter?"):]
            args = path.split("&")
            graph_name = args[0].split("=")[1]
            node_name = args[1].split("=")[1]
            attribute_name = args[2].split("=")[1]
            value = args[3].split("=")[1]
            self.server.app.change_parameter(graph_name, node_name, attribute_name, value)
            return



class PataServer:
    def __init__(self, args, app, host="localhost", port=4242):
        #        with open("./server/example.json") as f:
        #            self.example = json.load(f)
        # self.server.example = self.example
        self.app = app
        self.server = HTTPServer((host, port), SimpleHandler)
        self.server.app = app
        self.server.graphs_data = {}
        self.server.images = []
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True  # Allows program to exit even if thread is running

    def update(self):
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
