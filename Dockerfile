FROM python:3.12-alpine3.20

ENV OJ_ENV production

COPY . /app
WORKDIR /app

HEALTHCHECK --interval=5s --retries=3 CMD python3 /app/deploy/health_check.py

RUN apk add --no-cache \
    build-base \
    linux-headers \
    musl-dev \
    nginx \
    openssl \
    openssh \
    curl \
    unzip \
    supervisor \
    libjpeg-turbo-dev \
    zlib-dev \
    postgresql-dev \
    freetype-dev && \
    pip install --no-cache-dir -r /app/deploy/requirements.txt && \
    apk del build-base linux-headers musl-dev postgresql-dev

RUN mkdir dist
RUN curl -o dist.tar.gz http://203.250.33.103:31439/dcucode/latest.tar.gz   && \
    tar -xvzf dist.tar.gz -C dist && \
    rm dist.tar.gz

# ENTRYPOINT /app/deploy/entrypoint.sh
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]

