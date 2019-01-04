import os
import json
from bottle import get, put, run, request, response, error, HTTPResponse
from lib.sensor import Sensor
from lib.ir_client import IRClient
from lib.aircon import DaikinAircon

IR_WRITE_PIN = os.getenv('IR_WRITE_PIN', 19)

sensor = Sensor()
con = DaikinAircon()

@get('/env')
def env():
    t, h, p = sensor.fetch()
    return { 'temp': t, 'humidity': h, 'pressure': p }

@put('/aircon')
def aircon():
    try:
        work = 'work' in request.forms
        mode = request.forms['mode']
        temp = int(request.forms['temp'])
    except KeyError as ex:
        return HTTPResponse({'error': "missing parameter: {0}".format(ex.args[0])}, 400)

    try:
        code = con.pack(work=work, mode=mode, temp=temp)
        IRClient.send(code, IR_WRITE_PIN, con.carrier_freq)
    except ValueError as ex:
        return HTTPResponse({'error': str(ex)}, 400)
    return {'result': 'success'}

@error(404)
def error404(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '404 Not Found'})

@error(500)
def error500(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '500 Internal Server Error'})

run(host='0.0.0.0', port=os.getenv('PORT', 8080))
