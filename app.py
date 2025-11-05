# app.py （局部替换/合并）
import os, json, hashlib
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# 读取 codes.json 如你已实现
with open("codes.json","r") as f:
    CODES = json.load(f)

def save_codes():
    with open("codes.json","w") as f:
        json.dump(CODES, f, indent=2)

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

    # compute sha
    with open(path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()

    # minimal scan result (你可以改成调用 scanner.scan_file)
    # 如果已有 scanner.scan_file(path) 请把下面 result = ... 替换为 result = scan_file(path)
    import time
    result = {
        "sha": sha,
        "filename": filename,
        "received_at": time.time(),
        "simple_check": {
            "url_count": len(__import__('re').findall(r'https?://[^\s"\']+', data.decode(errors="ignore"))),
            "has_login_word": bool(__import__('re').search(r'\b(login|verify|password|account|reset)\b', data.decode(errors="ignore"), flags=__import__('re').I))
        }
    }

    # 持久化扫描结果到 results/<sha>.json
    result_path = os.path.join(app.config['RESULT_FOLDER'], f"{sha}.json")
    with open(result_path, "w", encoding="utf-8") as rf:
        json.dump(result, rf, ensure_ascii=False, indent=2)

    # 标记 code 为已使用并保存 codes.json
    CODES[code] = True
    save_codes()

    # 返回给前端 sha 和结果查看 URL
    host = request.host_url.rstrip("/")  # 自动生成基础URL
    view_url = f"{host}/result/{sha}"
    return jsonify({"status":"success", "sha": sha, "view_url": view_url})



