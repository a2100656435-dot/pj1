import os, io, time, secrets
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from fpdf import FPDF
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image
import pytesseract
import docx

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PDF_FOLDER'] = 'pdfs'
app.config['MAX_CONTENT_LENGTH'] = 20*1024*1024  # 20MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','txt','doc','docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(path, ext):
    ext = ext.lower()
    text=""
    try:
        if ext=='pdf':
            text = pdf_extract_text(path)
            if not text.strip():
                img = Image.open(path).convert("RGB")
                text = pytesseract.image_to_string(img, lang="chi_sim")
        elif ext=='txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text=f.read()
        elif ext in ('doc','docx'):
            doc = docx.Document(path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ('png','jpg','jpeg'):
            img = Image.open(path).convert("L")
            text = pytesseract.image_to_string(img, lang="chi_sim")
    except Exception as e:
        print("Extract text error:", e)
        text="[Error extracting text]"
    return text

def generate_pdf(text, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu","", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu","",12)
    max_len=90
    for line in text.splitlines():
        while len(line)>max_len:
            pdf.multi_cell(0,8,line[:max_len])
            line=line[max_len:]
        pdf.multi_cell(0,8,line)
    pdf_path=os.path.join(app.config['PDF_FOLDER'],filename)
    pdf.output(pdf_path)
    return pdf_path

# --- 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload',methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"status":"error","message":"No file part"}),400
    file = request.files['file']
    if file.filename=='':
        return jsonify({"status":"error","message":"No selected file"}),400
    if not allowed_file(file.filename):
        return jsonify({"status":"error","message":"File type not allowed"}),400

    filename=secure_filename(file.filename)
    ext=filename.rsplit('.',1)[1].lower()
    path=os.path.join(app.config['UPLOAD_FOLDER'],filename)
    file.save(path)

    text = extract_text(path, ext)
    timestamp=int(time.time())
    randstr=secrets.token_hex(4)
    pdf_filename=f"{timestamp}_{randstr}.pdf"
    pdf_path = generate_pdf(text, pdf_filename)

    os.remove(path)
    return jsonify({"status":"success","pdf_url":f"/pdf/{pdf_filename}"})

@app.route('/pdf/<pdf_name>')
def view_pdf(pdf_name):
    path=os.path.join(app.config['PDF_FOLDER'],pdf_name)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False)

@app.route('/admin')
def admin_dashboard():
    pdfs=[f for f in os.listdir(app.config['PDF_FOLDER']) if f.lower().endswith(".pdf")]
    pdfs.sort(reverse=True)
    return render_template('admin.html', pdfs=pdfs)

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))








