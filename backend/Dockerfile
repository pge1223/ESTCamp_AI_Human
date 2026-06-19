FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
# Cloud Run이 $PORT(기본 8080)를 주입한다
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
