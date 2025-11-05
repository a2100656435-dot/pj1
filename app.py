import os, json, hashlib, re, time
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

CODES_FILE = "codes.json"

# 初始化 codes.json，如果不存在
if not os.path.exists(CODES_FILE):
    with open(CODES_FILE, "w") as f:
        json.dump({"TEST001": False, "TEST002": False}, f)

with open(CODES_FILE, "r") as f:
    CODES = json.load(f)

def save_codes():
    with open(CODES_FILE, "w") as f:
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

    # 计算 SHA
    with open(path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()

    # 简单扫描示例
    text = data.decode(errors="ignore")
    result = {
        "sha": sha,
        "filename": filename,
        "url_count": len(re.findall(r'https?://[^\s"\']+', text)),
        "suspicious_keywords": re.findall(r'\b(login|verify|password|account|reset)\b', text, flags=re.I)
    }

    # 保存扫描结果
    result_path = os.path.join(app.config['RESULT_FOLDER'], f"{sha}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 标记 code 已使用
    CODES[code] = True
    save_codes()

    return jsonify({"status":"success", "result": result})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)






