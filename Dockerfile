FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# System deps for pdf2image + OpenCV
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["python", "app.py"]
