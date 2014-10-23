import json
import time

import gevent
import redis
from flask import Flask
from flask import jsonify
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
client_type = ['lpolling', 'sse', 'ws']
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


def lpolling_notify():
    app.event.wait()
    return 'ready'


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


def ws_notify():
    ws = request.environ.get('wsgi.websocket', None)
    if ws:
        while True:
            app.event.wait()
            ws.send('ready')
    else:
        raise RuntimeError("Environment lacks WSGI WebSocket support")


notify_methods = {
    'lpolling': lpolling_notify,
    'sse': sse_notify,
    'ws': ws_notify
    }


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
    chats = r.zrevrangebyscore('chats', float('inf'), min)
    timestamp = time.time()
    update_string = ''
    for chat in chats:
        chat = json.loads(chat)
        time_string = time.strftime('%a, %d %b %Y %H:%M:%S %Z',
                                    time.localtime(float(chat['timestamp'])))
        update_string += '{0}@{1}\n\t{2}\n'.format(
            chat['name'].encode('utf-8'),
            time_string,
            chat['words'].encode('utf-8'))
    return jsonify({'timestamp': timestamp, 'data': update_string})


@app.route('/notify')
@app.route('/notify/<type>')
def notity(type=None):
    if type not in client_type:
        type = client_type[0]
    return notify_methods[type]()


@run_with_reloader
def run_server():
    app.debug = True
    server = WSGIServer(("", 5002), app, handler_class=WebSocketHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
