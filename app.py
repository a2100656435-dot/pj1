import os, json, hashlib, re, time
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from fpdf import FPDF
import secrets, string

# PDF 解析
from pdfminer.high_level import extract_text

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
app.config['PDF_FOLDER'] = 'pdfs'

for d in [app.config['UPLOAD_FOLDER'], app.config['RESULT_FOLDER'], app.config['PDF_FOLDER']]:
    os.makedirs(d, exist_ok=True)

CODES_FILE = "codes.json"
ADMIN_KEY = os.getenv("ADMIN_KEY","change_me_to_secure_key")

# ===== PIN 管理 =====
if not os.path.exists(CODES_FILE):
    with open(CODES_FILE,"w") as f:
        json.dump([],f)

def load_codes():
    with open(CODES_FILE,"r") as f:
        return json.load(f)

def save_codes(codes):
    with open(CODES_FILE,"w") as f:
        json.dump(codes,f,indent=2)

def make_hash(salt_hex:str,pin_plain:str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.sha256(salt+pin_plain.encode()).hexdigest()

def generate_single_pin(length=10):
    alphabet = string.ascii_letters+string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_codes_batch(n=100,length=10):
    codes = load_codes()
    new_plain = []
    for _ in range(n):
        pin = generate_single_pin(length)
        salt = secrets.token_hex(16)
        h = make_hash(salt,pin)
        codes.append({"hash":h,"salt":salt,"status":"unused","created_at":int(time.time())})
        new_plain.append(pin)
    save_codes(codes)
    return new_plain

def invalidate_all_codes():
    codes = load_codes()
    for c in codes:
        c["status"]="expired"
    save_codes(codes)
    return len(codes)

def verify_and_consume_code(pin_plain:str):
    codes = load_codes()
    for i,rec in enumerate(codes):
        if rec.get("status") in ("used","expired"):
            continue
        if make_hash(rec["salt"],pin_plain)==rec["hash"]:
            codes[i]["status"]="used"
            codes[i]["used_at"]=int(time.time())
            save_codes(codes)
            return True
    return False

# ===== 管理接口 =====
from functools import wraps
def require_admin(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        key = request.headers.get("X-Admin-Key") or request.args.get("admin_key")
        if not key or key!=ADMIN_KEY:
            abort(401)
        return f(*args,**kwargs)
    return wrapper

@app.route("/admin/regenerate_codes",methods=["POST"])
@require_admin
def admin_regenerate_codes():
    try:
        body = request.get_json(force=True) or {}
        count = int(body.get("count",100))
        length = int(body.get("length",10))
        n_old = invalidate_all_codes()
        new_plain = generate_codes_batch(n=count,length=length)
        return jsonify({"status":"ok","expired_old":n_old,"generated_count":len(new_plain),"pins":new_plain})
    except Exception as e:
        import traceback
        return jsonify({"status":"error","message":str(e),"trace":traceback.format_exc()}),500

# ===== 前端页面 =====
@app.route('/')
def index():
    return render_template('index.html')

# ===== 上传 + 扫描 + PDF =====
@app.route('/upload',methods=['POST'])
def upload():
    try:
        code = request.form.get('code')
        file = request.files.get('file')
        if not code or not verify_and_consume_code(code):
            return jsonify({"status":"error","message":"invalid or used code"}),400
        if not file:
            return jsonify({"status":"error","message":"no file"}),400

        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'],filename)
        os.makedirs(app.config['UPLOAD_FOLDER'],exist_ok=True)
        file.save(path)

        # SHA
        with open(path,"rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()

        # 提取文本
        try:
            if filename.lower().endswith('.pdf'):
                text = extract_text(path)
            else:
                text = data.decode(errors="ignore")
        except Exception:
            text = ""

        # 扫描 URL + 可疑关键词
        urls = re.findall(r'https?://[^\s"\']+',text)
        keywords = re.findall(r'\b(login|verify|password|account|reset)\b',text,flags=re.I)
        result = {"sha":sha,"filename":filename,"url_count":len(urls),"suspicious_keywords":keywords}

        # 保存 JSON
        os.makedirs(app.config['RESULT_FOLDER'],exist_ok=True)
        result_path = os.path.join(app.config['RESULT_FOLDER'],f"{sha}.json")
        with open(result_path,"w",encoding="utf-8") as f:
            json.dump(result,f,indent=2,ensure_ascii=False)

        # 生成 PDF
        os.makedirs(app.config['PDF_FOLDER'],exist_ok=True)
        pdf_path = os.path.join(app.config['PDF_FOLDER'],f"{sha}.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial","B",16)
        pdf.cell(0,10,"Scan Result",0,1)
        pdf.set_font("Arial","",12)
        pdf.cell(0,10,f"Filename: {filename}",0,1)
        pdf.cell(0,10,f"SHA256: {sha}",0,1)
        pdf.cell(0,10,f"URLs found: {len(urls)}",0,1)
        pdf.cell(0,10,f"Suspicious keywords: {', '.join(keywords) if keywords else 'None'}",0,1)
        pdf.output(pdf_path)

        return jsonify({"status":"success","result":result,"pdf_url":f"/pdf/{sha}"})
    except Exception as e:
        import traceback
        return jsonify({"status":"error","message":str(e),"trace":traceback.format_exc()}),500

# ===== PDF 查看 =====
@app.route('/pdf/<sha>')
def view_pdf(sha):
    pdf_path = os.path.join(app.config['PDF_FOLDER'],f"{sha}.pdf")
    if not os.path.exists(pdf_path):
        abort(404)
    return send_file(pdf_path,as_attachment=False)

# ===== 启动 =====
if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)








