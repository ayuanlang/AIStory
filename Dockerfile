# ---- Stage 1: Build React Frontend (Vite) ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# 拷贝并安装前端依赖 (利用 npmmirror 加速)
COPY frontend/package*.json ./
RUN npm config set registry https://registry.npmmirror.com/ && npm install

# 拷贝所有前端源码并打包 (Vite 默认输出到 dist)
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Build FastAPI Backend ----
FROM python:3.13.5-slim
WORKDIR /app

# 防止 Python 字节码缓存和控制台输出缓冲
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装后端依赖 (利用阿里云源加速)
# agentscope (Python >=3.11) is optional on Render 3.10; install here for Docker 3.13.
COPY backend/requirements.txt backend/requirements-agentscope.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt -r ./backend/requirements-agentscope.txt -i https://mirrors.aliyun.com/pypi/simple/

# 拷贝后端业务代码
COPY backend/ ./backend/

# 从第一阶段中将打包好的网页拷贝给后端的挂载目录
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 设置工作目录至后端并暴露端口
WORKDIR /app/backend
ENV PORT=8000
EXPOSE $PORT

# 启动 FastAPI (它会自动发现并挂载上一层 ../frontend/dist 的入口网页)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
