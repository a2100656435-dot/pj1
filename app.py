from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os, json, hashlib, requests
from scanner import scan_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'eml', 'html', 'htm', 'txt'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 读取身份码列表
with open("codes.json", "r") as f:
    CODES = json.load(f)  # 结构: {"ABC123": false, "XYZ789": true} (true=已用)

def save_codes():
    with open("codes.json", "w") as f:
        json.dump(CODES, f, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    code = request.form.get('code')
    file = request.files.get('file')

    # 1️⃣ 验证身份码
    if not code or code not in CODES:
        return jsonify({"status": "error", "message": "无效身份码"}), 400
    if CODES[code]:
        return jsonify({"status": "error", "message": "此身份码已被使用"}), 400

    # 2️⃣ 验证文件
    if not file or not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "文件类型不允许"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    # 3️⃣ 执行扫描
    result = scan_file(path)

    # 4️⃣ 发送结果到队友的 API（示例）
    try:
        api_resp = requests.post(
            "https://example.com/receive",  # ← 改成你队友的API地址
            json={"code": code, "scan_result": result},
            timeout=5
        )
        api_status = api_resp.status_code
    except Exception as e:
        api_status = f"发送失败: {e}"

    # 5️⃣ 标记身份码为已使用
    CODES[code] = True
    save_codes()

    # 6️⃣ 返回结果
    return jsonify({
        "status": "success",
        "message": "上传成功，感谢提交！",
        "api_status": api_status,
        "scan_result": result
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
