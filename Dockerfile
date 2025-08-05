FROM ubuntu:22.04

# 设置时区和非交互模式
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# 安装编译依赖和基础包
RUN apt-get update && \
    apt-get install -y \
        wget \
        build-essential \
        zlib1g-dev \
        libncurses5-dev \
        libgdbm-dev \
        libnss3-dev \
        libssl-dev \
        libreadline-dev \
        libffi-dev \
        libsqlite3-dev \
        libbz2-dev \
        git \
        python3-pip \
        python3-venv \
        xvfb \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0 && \
    # 下载并编译 Python 3.12
    wget https://www.python.org/ftp/python/3.12.0/Python-3.12.0.tgz && \
    tar -xzf Python-3.12.0.tgz && \
    cd Python-3.12.0 && \
    ./configure --enable-optimizations --prefix=/usr/local && \
    make -j$(nproc) && \
    make altinstall && \
    # 清理编译文件
    cd .. && \
    rm -rf Python-3.12.0 Python-3.12.0.tgz && \
    # 清理APT缓存
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 创建非特权用户
RUN useradd -m -u 1000 appuser
USER appuser
WORKDIR /home/appuser

# 克隆项目
# 增加ADD这行，防止git clone 被cached
ADD https://api.github.com/repos/Arronlong/2apiBridge/git/refs/heads/master /tmp/always-fresh.json
# 添加了/get_token接口，添加了流式响应支持，增加VALID_API_KEY。
RUN git clone --depth 1 https://github.com/Arronlong/2apiBridge.git

# Python依赖安装
RUN cd 2apiBridge && \
    git submodule update --init --recursive && \
    /usr/local/bin/python3.12 -m venv .venv && \
    .venv/bin/python -m pip install --upgrade pip wheel setuptools && \
    .venv/bin/python -m pip install -e . && \
    .venv/bin/python -m pip install -r Turnstile-Solver/requirements.txt

# 构建时运行fetch
RUN cd 2apiBridge/Turnstile-Solver && \
    ../.venv/bin/python -m camoufox fetch

# 运行时配置
WORKDIR /home/appuser/2apiBridge

# 生成 .env，供 python-dotenv 读取
RUN echo "VALID_API_KEY=${VALID_API_KEY}" > .env
RUN echo "VALID_API_KEY=${VALID_API_KEY}" >> .env
RUN echo "VALID_API_KEY=${VALID_API_KEY}" >.> .env

# 启动脚本
ENTRYPOINT [".venv/bin/python", "2api_bridge.py"]
