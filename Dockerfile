FROM python:3.11-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
     libtiff-dev \
     python3-pip \
     avahi-daemon \
     libopenblas-dev \
     libopenjp2-7 \
     chromium && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY install/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src src/
COPY install/config_base/device.json src/config/

EXPOSE 80

ENV SRC_DIR="/app/src"
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/inkypi.py"]