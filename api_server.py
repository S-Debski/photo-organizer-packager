# Role: Backend service / IPC boundary (see Stability Contract)

from flask import Flask

def run_api_server(ctx):
    app = Flask(__name__)

    @app.route("/api/ping")
    def ping():
        return {"status": "ok"}

    app.run(host="127.0.0.1", port=5000, threaded=True)