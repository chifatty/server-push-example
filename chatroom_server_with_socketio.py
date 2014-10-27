import json
import time

import redis
from flask import Flask
from flask import render_template
from flask import request
from flask.ext.socketio import emit
from flask.ext.socketio import SocketIO
from gevent import monkey
from gevent.event import Event

app = Flask(__name__)
app.event = Event()
socketio = SocketIO(app)
monkey.patch_all()
redis_pool = redis.ConnectionPool()


@app.route('/')
def index():
    return render_template('chatroom_client_socketio.html',
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


@socketio.on('waiting_for_update', namespace='/test')
def handle_wait_update(message):
    try:
        min = message['min']
    except (KeyError, TypeError):
        min = 0
    r = redis.Redis(connection_pool=redis_pool)
    chats = []
    while not chats:
        timestamp = time.time()
        chats = r.zrangebyscore('chats', min, float('inf'))
        min = timestamp
        if not chats:
            app.event.wait()

    update_string = ''
    for chat in chats:
        chat = json.loads(chat)
        time_string = time.strftime('%H:%M:%S %Z',
                                    time.localtime(float(chat['timestamp'])))
        update_string += '[{0}]  {1:10}  said: {2}\n'.format(
            time_string,
            chat['name'].encode('utf-8'),
            chat['words'].encode('utf-8'))
    emit('update', json.dumps({'timestamp': timestamp, 'data': update_string}))


if __name__ == "__main__":
    app.debug = True
    socketio.run(app, host="0.0.0.0", port=5004)
