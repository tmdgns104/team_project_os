FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROJECT_OS_ENV=production \
    PROJECT_OS_DB=/data/project_os.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system projectos && adduser --system --ingroup projectos projectos \
    && mkdir -p /data \
    && chown projectos:projectos /data
COPY --chown=projectos:projectos app ./app
VOLUME ["/data"]
EXPOSE 8000
USER projectos
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=3).read()"]
CMD ["uvicorn", "app.main_v016:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--timeout-keep-alive", "10"]
