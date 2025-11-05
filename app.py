from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os, hashlib, json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 简单 codes.json 读取（确保 repo 根有此文件）
with open("codes.json","r") as f:
    CODES = json.load(f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    code = request.form.get('code')
    file = request.files.get('file')
    if not code or code not in CODES or CODES[code]:
        return jsonify({"status":"error","message":"invalid or used code"}), 400
    if not file:
        return jsonify({"status":"error","message":"no file"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    sha = hashlib.sha256(open(path,'rb').read()).hexdigest()
    CODES[code] = True
    with open("codes.json","w") as f:
        json.dump(CODES,f,indent=2)
    return jsonify({"status":"success","sha":sha})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

