import gevent
import time
from flask import Flask
from flask import render_template
from flask import request
from flask import Response
from gevent.wsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler  # For websocket

app = Flask(__name__)
client_type = ['polling', 'lpolling', 'sse', 'ws']


# SSE "protocol" is described here: http://mzl.la/UPFyxY
class ServerSentEvent(object):

    def __init__(self, data):
        self.data = data
        self.event = None
        self.id = None
        self.desc_map = {
            self.data: "data",
            self.event: "event",
            self.id: "id"
        }

    def encode(self):
        if not self.data:
            return ""
        lines = ["%s: %s" % (v, k)
                 for k, v in self.desc_map.iteritems() if k]

        return "%s\n\n" % "\n".join(lines)


@app.route('/polling_notify')
def polling_notify():
    return 'ready'


@app.route('/lpolling_notify', methods=['POST'])
def lpolling_notify():
    gevent.sleep(3)
    return 'ready'


@app.route('/sse_notify')
def sse_notify():
    def ready():
        try:
            while True:
                gevent.sleep(3)
                ev = ServerSentEvent(str('ready'))
                yield ev.encode()
        except GeneratorExit:
            pass

    return Response(ready(), mimetype="text/event-stream")


@app.route('/ws_notify')
def ws_notify():
    ws = request.environ.get('wsgi.websocket', None)
    if ws:
        while True:
            gevent.sleep(3)
            ws.send('ready')
    else:
        raise RuntimeError("Environment lacks WSGI WebSocket support")


@app.route('/')
@app.route('/type/<type>')
def index(type=None):
    if type not in client_type:
        type = client_type[0]
    return render_template('time_client_{0}.html'.format(type))


@app.route('/update')
def update():
    return time.strftime('%a, %d %b %Y %H:%M:%S %Z')

if __name__ == "__main__":
    app.debug = True
    #  server = WSGIServer(("", 5001), app)
    server = WSGIServer(("", 5001), app, handler_class=WebSocketHandler)
    server.serve_forever()
