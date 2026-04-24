FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 Python 缓冲 stdout 和生成 .pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 将 requirements.txt 拷贝到容器中
COPY requirements.txt .

# 安装依赖，使用阿里云等国内镜像加速
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 拷贝后端的所有代码
COPY . .

# 暴露端口，Render 默认使用环境变量 PORT 注入，未提供时默认 8000
ENV PORT=8000
EXPOSE $PORT

# 启动 FastAPI 应用 (假设你的主入口是 app/main.py 或 app.main)
# Render 或阿里云会通过修改环境变量的方式修改 PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
