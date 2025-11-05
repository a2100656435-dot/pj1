# 使用官方 Python 3.11 slim 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器
COPY . /app

# 安装依赖
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 创建必要目录
RUN mkdir -p uploads pdfs fonts

# 暴露 Flask 默认端口
EXPOSE 5000

# 容器启动 Flask
CMD ["python", "app.py"]
