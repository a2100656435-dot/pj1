import os, secrets, time, io, re
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image
import pytesseract
import docx
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch

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
                text = pdf_ocr_text(path, lang='chi_sim')
        elif ext=='txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text = f.read()
        elif ext in ('doc','docx'):
            doc_obj = docx.Document(path)
            text = '\n'.join([p.text for p in doc_obj.paragraphs])
        elif ext in ('png','jpg','jpeg'):
            img = Image.open(path).convert('L')
            img = img.point(lambda x:0 if x<128 else 255,'1')
            text = pytesseract.image_to_string(img, lang='chi_sim')
    except Exception as e:
        print("Extract text error:", e)
        text=""
    return text

# --- 生成 PDF (ReportLab) ---
def generate_pdf(text, filename):
    text = re.sub(r'[\x00-\x1F\x7F]', '', text).strip()
    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)
    os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)

    font_path = "fonts/DejaVuSans12.ttf"
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font file not found: {font_path}")
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.fontName = 'DejaVu'
    style.fontSize = 11
    style.leading = 16

    story = []
    story.append(Paragraph("<b>Scan Result</b><br/><br/>", style))

    for para in text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para.replace("\n", "<br/>"), style))
            story.append(Spacer(1, 0.2*inch))

    doc.build(story)
    return pdf_path

# --- 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload',methods=['POST'])
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

        os.remove(path)  # 删除临时文件

        return jsonify({"status":"success","pdf_url":f"/pdf/{pdf_filename}"})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status":"error","message":"Internal server error","trace":traceback.format_exc()}),500

@app.route('/pdf/<pdf_name>')
def view_pdf(pdf_name):
    path = os.path.join(app.config['PDF_FOLDER'],pdf_name)
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






