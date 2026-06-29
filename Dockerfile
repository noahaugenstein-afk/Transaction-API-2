FROM python:3.12-slim

WORKDIR /app

# System deps: pdfplumber/pypdf are pure-python; nothing extra needed for the
# core fill path. (poppler only needed if you add OCR later.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway/most hosts inject $PORT. Default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
