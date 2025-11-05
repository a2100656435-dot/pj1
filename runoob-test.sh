project/
 ├─ app.py                  # 主 Flask 应用
 ├─ requirements.txt        # Python 依赖
 ├─ runtime.txt             # 指定 Python 版本
 ├─ init_project.py         # 可选，初始化目录
 ├─ uploads/                # 临时上传文件（自动清理）
 ├─ pdfs/                   # 生成的 PDF 文件
 ├─ fonts/
 │    └─ DejaVuSans.ttf   # 用于 PDF 生成的 Unicode 字体
 └─ templates/
      ├─ index.html         # 用户上传页面
      └─ admin.html         # 管理端查看生成 PDF
