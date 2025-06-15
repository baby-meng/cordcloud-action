FROM python:3.10-slim

# 避免交互提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装 Playwright 所需依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libxshmfence1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 和 Chromium
RUN pip install --no-cache-dir playwright && \
    python -m playwright install --with-deps chromium

# 复制项目文件
COPY . /app

# 设置默认入口
CMD ["python", "app/action.py"]
