import time
import importlib
import logging

flask = importlib.import_module('flask')
Flask = flask.Flask
request = flask.request
make_response = flask.make_response
user_service = importlib.import_module('user_service')


if not hasattr(user_service, 'service'):
    exit(1)

app = Flask(__name__)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

times = {}


@app.route('/call', methods=['POST'])
def serverless():
    req = request.get_json(silent=True)
    if req is None:
        return make_response({'error': 'Request is not of json.'}, 400)
    s = time.time()
    res, code = user_service.service(req)
    t = time.time()
    times['call'].append((s, t))
    if type(res) is not dict or type(code) is not int:
        return make_response({'error': 'Loaded faulty service.'}, 500)
    return make_response(res, code)


@app.route('/times', methods=['GET'])
def get_times():
    return make_response(times, 200)


times['ready'] = time.time()
times['call'] = []
