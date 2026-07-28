FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor.py .
COPY servers.json .

RUN mkdir -p /app/backups

ENV PYTHONUNBUFFERED=1

CMD ["python3", "monitor.py"]
