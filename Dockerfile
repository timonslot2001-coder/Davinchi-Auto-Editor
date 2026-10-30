# AutoEdit Studio (web app). The editing itself runs on Windows through the worker (start-studio-docker.bat):
# DaVinci Resolve, the GPU for local AI, the footage and Edge for titles are on the Windows host.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir flask==3.1.3 waitress==3.0.2 requests==2.32.5 pyyaml==6.0.3
WORKDIR /app
COPY webapp/ webapp/
RUN useradd -m studio
USER studio
EXPOSE 5060
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:5060/')"
CMD ["python", "-m", "webapp", "--bind", "0.0.0.0", "--no-browser"]
