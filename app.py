from flask import Flask, request, jsonify
from flasgger import Swagger, swag_from

import os
import json
import tempfile
import numpy as np
import requests
from pdf2image import convert_from_path
from PIL import Image
import fitz  # PyMuPDF
from rapidocr_onnxruntime import RapidOCR


# =====================================
#  Base Flask App + Swagger
# =====================================
app = Flask(__name__)

app.config["SWAGGER"] = {
    "title": "Invoice OCR + LLM Extraction API",
    "uiversion": 3,
    "openapi": "3.0.2",
}

swagger = Swagger(app)

# =====================================
#  1) LLM Extraction (Ollama)
# =====================================

# لو Ollama شغال على نفس السيرفر برا Docker:
# خليه يبان للكونتينر بالـ run:
#   docker run ... --add-host=host.docker.internal:host-gateway ...
# وبعدين استخدم:
#OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
# ولو انت مش هتستخدم Docker للـ Ollama وبتشغله جوه نفس الكونتينر:
# خليه كده:
OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL = "llama3.1:8b"

EXTRACTION_SCHEMA = {
    "client_name": "",
    "iban": "",
    "total_amount": "",
    "invoice_number": "",
    "subtotal": "",
    "vat_amount": "",
    "bank_name": "",
    "beneficiary_name":""
}


def build_prompt(full_text: str):
    schema_str = json.dumps(EXTRACTION_SCHEMA, indent=2)
    return f"""
You are an information extraction AI specialized in invoices.

Extract ONLY the fields from the invoice text below.

Return valid JSON EXACTLY in this schema:

{schema_str}

Rules:
- No explanations.
- No extra text.
- No comments.
- Only JSON output.
- If a field is missing, return empty string.

### TEXT START ###
{full_text}
### TEXT END ###
"""


@swag_from({
    "tags": ["Extraction"],
    "summary": "Extract structured invoice data using Local LLM",
    "description": "Send OCR full_text and receive a structured JSON extracted by LLM.",
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "full_text": {
                            "type": "string",
                            "example": "Invoice No: 2025-0147 ... IBAN: AE123..."
                        }
                    }
                }
            }
        }
    },
    "responses": {
        200: {
            "description": "Extraction result as structured JSON"
        },
        400: {"description": "Bad Request"},
        500: {"description": "LLM returned invalid JSON"},
    }
})
@app.post("/extract")
def extract():
    data = request.get_json()
    if not data or "full_text" not in data:
        return jsonify({"error": "full_text missing"}), 400

    prompt = build_prompt(data["full_text"])

    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False}
    ).json()

    try:
        result_json = json.loads(response["response"])
        return jsonify(result_json)
    except Exception:
        return jsonify({
            "error": "LLM returned invalid JSON",
            "raw": response.get("response", "")
        }), 500


# =====================================
#  2) OCR API (RapidOCR)
# =====================================

rapid_ocr = RapidOCR()


def enhance_for_arabic(img: Image.Image) -> Image.Image:
    return img.point(lambda x: min(255, int(x * 1.35)))


def detect_pdf_quality(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    page = doc[0]

    if page.get_text().strip():
        return "text"

    if page.get_images(full=True):
        return "scanner"

    return "unknown"


def choose_dpi(pdf_path: str) -> int:
    quality = detect_pdf_quality(pdf_path)

    if quality == "text":
        print("[DPI] PDF contains digital text → DPI 130")
        return 130

    if quality == "scanner":
        print("[DPI] PDF is scanned → DPI 200")
        return 200

    print("[DPI] Unknown → DPI 180")
    return 180


def pdf_to_images(path: str):
    dpi = choose_dpi(path)
    return convert_from_path(path, dpi=dpi)


def smart_resize(img: Image.Image, min_width: int = 800, max_width: int = 1400) -> Image.Image:
    w, h = img.size

    if w > max_width:
        new_h = int(h * (max_width / w))
        return img.resize((max_width, new_h), Image.LANCZOS)

    if w < min_width:
        new_h = int(h * (min_width / w))
        return img.resize((min_width, new_h), Image.LANCZOS)

    return img


def normalize_image_mode(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img

    if img.mode in ["CMYK", "P", "LA", "1", "RGBA"]:
        return img.convert("RGB")

    return img.convert("RGB")


def load_image(path: str):
    img = Image.open(path)
    frames = []

    try:
        for i in range(getattr(img, "n_frames", 1)):
            img.seek(i)
            frame = img.copy()

            if frame.mode in ["CMYK", "P", "LA", "1"]:
                frame = frame.convert("RGB")

            frames.append(frame)

    except Exception:
        frame = img
        if frame.mode != "RGB":
            frame = frame.convert("RGB")
        frames = [frame]

    return frames


def parse_result(ocr_result):
    parsed = []
    if not ocr_result:
        return parsed

    for line in ocr_result:
        try:
            box, text, score = line
            box_int = [[int(x), int(y)] for x, y in box]
            parsed.append({
                "text": str(text),
                "confidence": float(score),
                "box": box_int
            })
        except Exception:
            continue

    return parsed


@swag_from({
    "tags": ["OCR"],
    "summary": "Extract text from files (PDF / TIF / Images) using RapidOCR",
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary"
                        }
                    }
                }
            }
        }
    },
    "responses": {
        200: {"description": "OCR extracted successfully"}
    }
})
@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    if "file" not in request.files:
        return jsonify({"error": "upload a file"}), 400

    f = request.files["file"]
    ext = os.path.splitext(f.filename.lower())[1]

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    f.save(tmp.name)

    pages_output = []

    try:
        if ext == ".pdf":
            pages = pdf_to_images(tmp.name)
        else:
            pages = load_image(tmp.name)

        for i, img in enumerate(pages, start=1):
            img = normalize_image_mode(img)
            img = smart_resize(img)
            img = enhance_for_arabic(img)

            img_np = np.array(img)
            img_bgr = img_np[:, :, ::-1]

            ocr_result, infer_cost = rapid_ocr(img_bgr)

            results = parse_result(ocr_result)
            full_text = " ".join(r["text"] for r in results)

            pages_output.append({
                "page_index": i,
                "full_text": full_text,
                "results": results,
                "timing": {
                    "det": infer_cost[0] if infer_cost else None,
                    "cls": infer_cost[1] if infer_cost else None,
                    "rec": infer_cost[2] if infer_cost else None,
                }
            })
    finally:
        os.remove(tmp.name)

    return jsonify({
        "total_pages": len(pages_output),
        "pages": pages_output
    })


# =====================================
#  Home
# =====================================
@app.get("/")
def home():
    return {
        "msg": "OK — combined API running",
        "endpoints": ["/ocr", "/extract"],
        "docs": "/apidocs"
    }


if __name__ == "__main__":
    # تقدر تغير البورت لو حابب
    app.run(host="0.0.0.0", port=8000)
