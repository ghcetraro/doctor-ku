FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts /scripts

ENV CONFIG_PATH=/config/clusters.yaml
ENV HOST=0.0.0.0
ENV PORT=8080
ENV TZ=America/Argentina/Buenos_Aires
ENV SSH_KEYS_DIR=/secrets/ssh
ENV SCRIPTS_DIR=/scripts
ENV LOG_LEVEL=INFO
ENV STATE_PATH=/data/state.json

CMD ["python", "-m", "app.runner"]
