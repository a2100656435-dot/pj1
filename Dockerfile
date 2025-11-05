# 使用稳定 Python 3.11
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 拷贝项目文件
COPY . /app

# 升级 pip 并安装依赖
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 5000

# 启动 Flask
CMD ["python", "app.py"]
