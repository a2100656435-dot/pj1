import os, io
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text as pdf_extract_text
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import docx
import fitz  # PyMuPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','txt','doc','docx'}

# 你系统安装 Tesseract 后，如果在 Windows，需要指定路径
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- OCR 图片预处理 ----------
def ocr_image(img: Image.Image, lang='chi_sim+eng'):
    img = img.convert('L')  # 灰度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)  # 提高对比度
    img = img.filter(ImageFilter.SHARPEN)
    # 保留灰度，不强制二值化
    text = pytesseract.image_to_string(img, lang=lang)
    return text

# ---------- PDF OCR ----------
def pdf_ocr_text(path, lang='chi_sim+eng'):
    doc = fitz.open(path)
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes()))
        full_text += ocr_image(img, lang) + "\n"
    return full_text

# ---------- 提取文字 ----------
def extract_text(path, ext):
    ext = ext.lower()
    text = ""
    try:
        if ext=='pdf':
            text = pdf_extract_text(path)
            if not text.strip():
                text = pdf_ocr_text(path)
        elif ext=='txt':
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                text = f.read()
        elif ext in ('doc','docx'):
            doc = docx.Document(path)
            text = '\n'.join([p.text for p in doc.paragraphs])
        elif ext in ('png','jpg','jpeg'):
            img = Image.open(path)
            text = ocr_image(img)
    except Exception as e:
        import traceback
        print("Extract text error:", e)
        print(traceback.format_exc())
        text = "[Error extracting text]"
    return text

# ---------- 路由 ----------
@app.route('/')
def index():
    return render_template('index.html')  # 浏览器上传页面

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"status":"error","message":"No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status":"error","message":"No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"status":"error","message":"File type not allowed"}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.',1)[1].lower()
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    text = extract_text(path, ext)

    # 删除上传文件
    try:
        os.remove(path)
    except:
        pass

    return jsonify({"status":"success", "text": text})

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)))



