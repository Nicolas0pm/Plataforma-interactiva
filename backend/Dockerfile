# Imagen de la API (FastAPI) para desplegar en Render, Cloud Run o cualquier
# servicio que corra contenedores. Las credenciales NO van en la imagen: se pasan
# como variables de entorno (ver docs/despliegue.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Usuario sin privilegios
RUN useradd --create-home api && chown -R api /app
USER api

# Render y Cloud Run indican el puerto en $PORT
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
