from flask import Flask
from flask import request

app = Flask(__name__)
@app.route('/')
def index():
    lid=""
    cid = ""
    pid = ""
    requestkey = ""
    if request.method == 'GET':
        lid = request.args.get('lid')
        cid = request.args.get('cid')
        pid = request.args.get('pid')

    if request.method == 'POST':
        requestkey = request.form.get('rkey')

    if requestkey == 'rkey':
        return 'lid = %s, cid = %s, pid = %s'%(lid, cid, pid)
    else:
        return 'No request key'
    #if request.method == 'POST':
    #    data = request.form.get('cid')
    return 'Hello Flask'

if __name__ == '__main__':
    app.run(host='localhost', port=5555)