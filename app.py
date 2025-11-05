import os
import secrets
import time
import io
import re
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image
import pytesseract
import docx
import fitz  # PyMuPDF
from fpdf import FPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PDF_FOLDER'] = 'pdfs'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','txt','doc','docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# --- PDF OCR ---
def pdf_ocr_text(path, lang='eng'):
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        text = pytesseract.image_to_string(img, lang=lang)
        full_text += text + "\n"
    return full_text

# --- 提取文字 ---
def extract_text(path, ext):
    ext = ext.lower()
    text = ""
    try:
        if ext=='pdf':
            text = pdf_extract_text(path)
            if not text.strip():
                text = pdf_ocr_text(path, lang='chi_sim')  # 支持中文
        elif ext=='txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text = f.read()
        elif ext in ('doc','docx'):
            doc_file = docx.Document(path)
            text = '\n'.join([p.text for p in doc_file.paragraphs])
        elif ext in ('png','jpg','jpeg'):
            img = Image.open(path).convert('L')
            img = img.point(lambda x:0 if x<128 else 255,'1')
            text = pytesseract.image_to_string(img, lang='chi_sim')
    except Exception as e:
        print("Extract text error:", e)
        text=""
    return text

# --- 生成 Unicode PDF ---
def generate_pdf(text, filename):
    os.makedirs("pdfs", exist_ok=True)
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)

    def split_long_lines(text, max_len=90):
        lines=[]
        for line in text.splitlines():
            while len(line) > max_len:
                lines.append(line[:max_len])
                line = line[max_len:]
            lines.append(line)
        return lines

    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            self.add_page()
            self.add_font('DejaVu', '', 'fonts/DejaVuSans.ttf', uni=True)
            self.set_font('DejaVu', '', 12)
            self.set_auto_page_break(auto=True, margin=15)

        def safe_multi_cell(self, txt):
            for line in split_long_lines(txt, max_len=90):
                try:
                    self.multi_cell(0, 8, line)
                except Exception:
                    self.multi_cell(0, 8, line.encode("utf-8","ignore").decode("utf-8"))

    pdf = PDF()
    pdf.multi_cell(0, 10, "Scan Result\n\n")
    paragraphs = text.split("\n\n")
    for para in paragraphs:
        pdf.safe_multi_cell(para + "\n")

    pdf_path = os.path.join("pdfs", filename)
    pdf.output(pdf_path)
    return pdf_path

# --- 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"status":"error","message":"No file part in request"}),400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status":"error","message":"No selected file"}),400
        if not allowed_file(file.filename):
            return jsonify({"status":"error","message":"File type not allowed"}),400

        filename = secure_filename(file.filename)
        ext = filename.rsplit('.',1)[1].lower()
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        text = extract_text(path, ext)

        timestamp = int(time.time())
        randstr = secrets.token_hex(4)
        pdf_filename = f"{timestamp}_{randstr}.pdf"
        pdf_path = generate_pdf(text, pdf_filename)

        try:
            os.remove(path)
        except Exception:
            pass

        return jsonify({"status":"success","pdf_url":f"/pdf/{pdf_filename}"})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status":"error","message":"Internal server error","trace":traceback.format_exc()}),500

@app.route('/pdf/<pdf_name>')
def view_pdf(pdf_name):
    path = os.path.join(app.config['PDF_FOLDER'], pdf_name)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False)

@app.route('/admin')
def admin_dashboard():
    pdfs = [f for f in os.listdir(app.config['PDF_FOLDER']) if f.lower().endswith('.pdf')]
    pdfs.sort(reverse=True)
    return render_template('admin.html', pdfs=pdfs)

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"status":"error","message":"Internal server error"}),500

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))









