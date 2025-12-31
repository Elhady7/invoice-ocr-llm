
# Invoice OCR + LLM Extraction API

A unified **Flask-based API** that combines **OCR** and **LLM-powered information extraction** into a single, production-ready service.

The system is designed specifically for **invoice processing**, with strong support for **Arabic documents**, and runs fully **locally** using **Ollama** (no external LLM APIs required).

---

## 🚀 Overview

This project merges two traditionally separate pipelines into one clean API:

1. **OCR Service**  
   Extracts text from PDFs and images using **RapidOCR**, with image preprocessing optimized for Arabic content.

2. **LLM Extraction Service**  
   Uses a **local LLM (Ollama)** to transform raw OCR text into a **structured JSON invoice schema**.

Both services are exposed under **one Flask app**, **one Docker container**, and **one Swagger UI**.

---

## ✨ Key Features

- Unified OCR + LLM API
- Arabic-friendly OCR preprocessing
- Smart PDF quality detection (digital vs scanned)
- Dynamic DPI selection for performance vs accuracy
- Structured JSON output enforced by schema
- Swagger UI for interactive testing
- Fully Dockerized
- Works entirely offline with local Ollama models

---

## 🧠 Architecture

```

PDF / Image
↓
Preprocessing (resize, normalize, enhance)
↓
RapidOCR
↓
Full Text + Bounding Boxes
↓
Prompted Local LLM (Ollama)
↓
Structured JSON (Invoice Fields)

````

---

## 🔌 API Endpoints

### 1. OCR Endpoint
**POST `/ocr`**

Uploads a PDF or image and returns OCR results.

**Response includes:**
- `full_text`
- Word-level bounding boxes
- Confidence scores
- OCR timing (det / cls / rec)
- Page-level breakdown

---

### 2. Extraction Endpoint
**POST `/extract`**

Transforms OCR text into structured invoice data using a local LLM.

**Request Body**
```json
{
  "full_text": "Invoice No 12345 ..."
}
````

**Response**

```json
{
  "client_name": "",
  "iban": "",
  "total_amount": "",
  "invoice_number": "",
  "subtotal": "",
  "vat_amount": "",
  "bank_name": "",
  "beneficiary_name": ""
}
```

Rules enforced:

* JSON only (no explanations)
* Fixed schema
* Missing fields return empty strings

---

### 3. Swagger UI

**GET `/apidocs`**

Interactive API documentation and testing interface.

---

## 🧾 Extraction Schema

The LLM is strictly constrained to output this schema:

```json
{
  "client_name": "",
  "iban": "",
  "total_amount": "",
  "invoice_number": "",
  "subtotal": "",
  "vat_amount": "",
  "bank_name": "",
  "beneficiary_name": ""
}
```

This ensures predictable, machine-consumable output.

---

## 🖼️ OCR Enhancements for Arabic

Several preprocessing steps were added to improve OCR accuracy:

* **Color normalization** (CMYK / RGBA → RGB)
* **Smart resizing** (min 800px, max 1400px width)
* **Brightness enhancement** for Arabic text
* **Automatic PDF quality detection**

  * Digital text → lower DPI
  * Scanned PDFs → higher DPI

This balances **speed, accuracy, and memory usage**.

---

## 🐳 Docker & Ollama Integration

### Why `--network=host`?

When running Ollama locally, Docker containers cannot access `localhost` by default.

On Linux (Fedora / Ubuntu), the most stable solution is:

```bash
--network=host
```

This allows the container to directly access:

```
http://localhost:11434
```

No extra networking hacks required.

---

## 🧩 Requirements

* Docker
* Ollama (running locally)
* Model available in Ollama:

  ```
  llama3.1:8b
  ```

---

## ▶️ Run Locally (Docker)

### 1. Make sure Ollama is running

```bash
curl http://localhost:11434/api/generate \
  -d '{"model":"llama3.1:8b","prompt":"hello","stream":false}'
```

### 2. Build the image

```bash
docker build -t invoice-ocr-llm .
```

### 3. Run the container

```bash
docker run -d --name invoice-ocr-llm --network=host invoice-ocr-llm
```

### 4. Open Swagger

```
http://localhost:8000/apidocs
```

---

## 🧪 Typical Usage Flow

1. Upload document to `/ocr`
2. Retrieve `full_text`
3. Send `full_text` to `/extract`
4. Receive structured invoice JSON

---

## 📂 Project Structure

```
.
├── app.py
├── Dockerfile
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚠️ Notes

* Designed and tested on Linux environments
* Uses Flask development server (sufficient for internal tools / POCs)
* Can be extended with Gunicorn, authentication, or async workers

---

## 🔮 Possible Extensions

* Multi-language invoice schemas
* Field-level confidence scoring
* RAG-based validation
* UI for visual OCR review
* Batch processing & queues
* CI/CD with GitHub Actions

---

## 📜 License

This project is provided as-is for research, internal tools, and prototyping purposes.

