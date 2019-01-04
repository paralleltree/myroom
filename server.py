import os
import json
from bottle import get, run, response, error
from lib.sensor import Sensor

sensor = Sensor()

@get('/env')
def env():
    t, h, p = sensor.fetch()
    return { 'temp': t, 'humidity': h, 'pressure': p }

@error(404)
def error404(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '404 Not Found'})

@error(500)
def error500(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '500 Internal Server Error'})

run(host='0.0.0.0', port=os.getenv('PORT', 8080))
