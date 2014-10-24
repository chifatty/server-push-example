import json
import time

import redis
from flask import Flask
from flask import jsonify
from flask import make_response
from flask import render_template
from flask import request
from flask import Response
from gevent import monkey
from gevent.event import Event
from gevent.wsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler  # For websocket
from werkzeug.serving import run_with_reloader

app = Flask(__name__)
app.event = Event()
monkey.patch_all()
client_type = ['polling', 'lpolling', 'sse', 'ws']
redis_pool = redis.ConnectionPool()


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


@app.route('/lpolling_notify', methods=['POST'])
def lpolling_notify():
    app.event.wait()
    return 'ready'


@app.route('/sse_notify')
def sse_notify():
    def ready():
        try:
            while True:
                app.event.wait()
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
            app.event.wait()
            ws.send('ready')
    else:
        raise RuntimeError("Environment lacks WSGI WebSocket support")


@app.route('/')
@app.route('/type/<type>')
def index(type=None):
    if type not in client_type:
        type = client_type[0]
    return render_template('chatroom_client_{0}.html'.format(type),
                           timestamp=time.time())


@app.route('/publish', methods=['POST'])
def publish():
    r = redis.Redis(connection_pool=redis_pool)
    d = json.dumps({
        'name': request.form.get('name', 'anonymous'),
        'words': request.form.get('words', ''),
        'timestamp': time.time()
    })
    r.zadd('chats', d, time.time())
    app.event.set()
    app.event.clear()
    return ''


@app.route('/update/<timestamp>')
def update(timestamp):
    try:
        min = float(timestamp)
    except ValueError:
        min = -float('inf')

    r = redis.Redis(connection_pool=redis_pool)
    chats = r.zrangebyscore('chats', min, float('inf'))
    timestamp = time.time()
    update_string = ''
    for chat in chats:
        chat = json.loads(chat)
        time_string = time.strftime('%H:%M:%S %Z',
                                    time.localtime(float(chat['timestamp'])))
        update_string += '[{0}]  {1:10}  said: {2}\n'.format(
            time_string,
            chat['name'].encode('utf-8'),
            chat['words'].encode('utf-8'))
    return jsonify({'timestamp': timestamp, 'data': update_string})


@run_with_reloader
def run_server():
    app.debug = True
    server = WSGIServer(("", 5002), app, handler_class=WebSocketHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
