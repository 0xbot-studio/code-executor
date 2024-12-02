FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY *.py .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt

COPY . .

ENV MAIN_PORT=18080
ENV METRICS_PORT=18000
ENV SERVER_HOST=0.0.0.0

EXPOSE $MAIN_PORT
EXPOSE $METRICS_PORT

CMD ["python", "server.py"]