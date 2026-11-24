FROM python:3.12-slim
WORKDIR /worker
ENV OTEL_SDK_DISABLED=true PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker.py .
CMD ["python", "worker.py"]
