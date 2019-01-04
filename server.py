import os
import json
from bottle import get, run, response, error

@error(404)
def error404(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '404 Not Found'})

@error(500)
def error500(error):
    response.content_type = 'application/json'
    return json.dumps({'error': '500 Internal Server Error'})

run(host='0.0.0.0', port=os.getenv('PORT', 8080))
