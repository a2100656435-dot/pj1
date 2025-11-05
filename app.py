import os, io, re, secrets, time
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image, ImageFilter
import pytesseract
import docx
import fitz  # PyMuPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','txt','doc','docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# --- PDF OCR ---
def pdf_ocr_text(path):
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)  # 提高 DPI
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        img = img.point(lambda x:0 if x<140 else 255, '1')  # 二值化
        img = img.filter(ImageFilter.SHARPEN)  # 锐化
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        full_text += text + "\n"
    return full_text

# --- 图片 OCR ---
def image_ocr_text(path):
    img = Image.open(path).convert("L")
    img = enhancer.enhance(2.0)  # 提升对比度
    img = img.point(lambda x:0 if x<140 else 255, '1')
    img = img.filter(ImageFilter.SHARPEN)
    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
    return text

# --- 提取文字 ---
def extract_text(path, ext):
    ext = ext.lower()
    text = ""
    try:
        if ext == 'pdf':
            text = pdf_extract_text(path)
            if not text.strip():
                text = pdf_ocr_text(path)
        elif ext in ('png','jpg','jpeg'):
            text = image_ocr_text(path)
        elif ext == 'txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text = f.read()
        elif ext in ('doc','docx'):
            doc_file = docx.Document(path)
            paragraphs = [p.text for p in doc_file.paragraphs]
            for table in doc_file.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    paragraphs.append(row_text)
            text = "\n".join(paragraphs)
        else:
            text = "[Unsupported file type]"
    except Exception as e:
        print("Extract text error:", e)
        text = "[Error extracting text]"

    # 自动标注超链接
    url_pattern = re.compile(r'(https?://[^\s]+)')
    text = url_pattern.sub(r'[链接: \1]', text)
    return text

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"status":"error","message":"No file part"}),400
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

        os.remove(path)
        return jsonify({"status":"success","text": text})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"status":"error","message":"Internal server error","trace":traceback.format_exc()}),500

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))




