# Image for both the API and the job worker (same code, different command).
#
# Ubuntu 24.04 gives the same LibreOffice build and font packages the renderer and visual QC are tested
# against. LibreOffice renders slide previews and powers visual QC. The fonts cover what teachers commonly
# use: metric-compatible Calibri/Cambria (Carlito/Caladea), Arial/Times (Liberation), Montserrat, Open Sans,
# Lato, Roboto, Comic Neue and Noto (including Noto Sans Arabic for RTL decks).
ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-venv ca-certificates curl \
        libreoffice-impress libreoffice-writer fontconfig \
        fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation2 fonts-dejavu-core \
        fonts-noto-core fonts-open-sans fonts-lato fonts-roboto fonts-comic-neue fonts-montserrat \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f \
    && python3 -m venv /opt/venv

WORKDIR /app

# Install dependencies from pyproject.toml first so code changes don't invalidate this layer.
COPY pyproject.toml constraints.txt ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); open('/tmp/requirements.txt', 'w').write(chr(10).join(d['project']['dependencies']))" \
    && pip install -r /tmp/requirements.txt -c constraints.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/var/storage \
    && chown -R app:app /app/var
USER app
ENV HOME=/home/app

EXPOSE 8000
# Trust X-Forwarded-For only from proxies on private networks (the web container, an internal load balancer);
# uvicorn uses the right-most address not in this list. The web app passes X-Forwarded-For through unchanged,
# so in production put a TLS proxy in front of it that sets the header (see docs/DEPLOYMENT.md).
ENV FORWARDED_ALLOW_IPS="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
