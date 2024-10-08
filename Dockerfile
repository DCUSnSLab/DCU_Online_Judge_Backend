FROM python:3.7-alpine3.9

ENV OJ_ENV production

ADD . /app
WORKDIR /app

RUN apk add gcc
RUN apk add linux-headers
RUN apk add musl-dev

HEALTHCHECK --interval=5s --retries=3 CMD python2 /app/deploy/health_check.py

RUN apk add --update --no-cache build-base nginx openssl curl unzip supervisor jpeg-dev zlib-dev postgresql-dev freetype-dev && \
    pip install --no-cache-dir -r /app/deploy/requirements.txt && \
    apk del build-base --purge

RUN mkdir dist
RUN curl -o dist.tar.gz http://203.250.33.103:31439/dcucode/latest.tar.gz   && \
    tar -xvzf dist.tar.gz -C dist && \
    rm dist.tar.gz

# ENTRYPOINT /app/deploy/entrypoint.sh
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]

