import os, io, time, secrets, re
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from fpdf import FPDF
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image
import pytesseract
import docx
import fitz  # PyMuPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PDF_FOLDER'] = 'pdfs'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','txt','doc','docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# --- OCR / 文本提取 ---
def extract_text(path, ext):
    ext = ext.lower()
    text = ""
    try:
        if ext == 'pdf':
            text = pdf_extract_text(path)
            if not text.strip():
                # 扫描 PDF 用 OCR
                text = ocr_pdf(path)
        elif ext in ('png','jpg','jpeg'):
            text = ocr_image(path)
        elif ext == 'txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text = f.read()
        elif ext in ('doc','docx'):
            doc = docx.Document(path)
            text = '\n'.join([p.text for p in doc.paragraphs])
    except Exception as e:
        print("Extract error:", e)
        text = ""
    return mark_links(text)

# --- OCR 图片 ---
def ocr_image(path, lang='chi_sim+eng'):
    img = Image.open(path)
    img = img.convert('L').point(lambda x: 0 if x<140 else 255, '1')  # 二值化
    return pytesseract.image_to_string(img, lang=lang)

# --- OCR PDF ---
def ocr_pdf(path, lang='chi_sim+eng'):
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes()))
        full_text += pytesseract.image_to_string(img, lang=lang) + "\n"
    return full_text

# --- 标注超链接 ---
def mark_links(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, r'[链接: \1]', text)

# --- 生成 Unicode PDF，保留排版 ---
def generate_pdf(text, filename):
    os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            self.add_font('DejaVu', '', 'fonts/DejaVuSans.ttf', uni=True)
            self.set_font('DejaVu', '', 11)
            self.set_auto_page_break(auto=True, margin=15)
            self.add_page()
        def safe_write(self, txt):
            max_len = 120
            for line in txt.splitlines():
                while len(line) > max_len:
                    self.multi_cell(0,8,line[:max_len])
                    line=line[max_len:]
                self.multi_cell(0,8,line)

    pdf = PDF()
    pdf.safe_write("扫描结果\n\n")
    for p in text.split("\n\n"):
        pdf.safe_write(p + "\n")
    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

# --- 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload',methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"status":"error","message":"未上传文件"}),400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status":"error","message":"未选择文件"}),400
        if not allowed_file(file.filename):
            return jsonify({"status":"error","message":"文件类型不允许"}),400

        filename = secure_filename(file.filename)
        ext = filename.rsplit('.',1)[1].lower()
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        # 提取文本
        text = extract_text(path, ext)

        # 生成 PDF
        pdf_filename = f"{int(time.time())}_{secrets.token_hex(4)}.pdf"
        try:
            pdf_path = generate_pdf(text, pdf_filename)
        except Exception as e:
            print("PDF生成失败:", e)
            return jsonify({"status":"error","message":"PDF生成失败"}),500
        finally:
            try:
                os.remove(path)
            except:
                pass

        return jsonify({"status":"success","pdf_url":f"/pdf/{pdf_filename}"})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status":"error","message":"服务器错误","trace":traceback.format_exc()}),500

@app.route('/pdf/<pdf_name>')
def view_pdf(pdf_name):
    path = os.path.join(app.config['PDF_FOLDER'],pdf_name)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False)

@app.route('/admin')
def admin():
    pdfs = [f for f in os.listdir(app.config['PDF_FOLDER']) if f.lower().endswith('.pdf')]
    pdfs.sort(reverse=True)
    return render_template('admin.html', pdfs=pdfs)

if __name__=="__main__":
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))





