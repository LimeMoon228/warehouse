"""Веб-адаптер над ocr.py и llm.py по контракту docs/PACKING-ADAPTER.md.

Настройки (PACKING_HOST, PACKING_PORT, PACKING_API_KEY, LLM_URL, LLM_MODEL, OCR_DEVICE) — в .env.
Запуск: python -m packing_service.api
"""

import os
import secrets
import threading

import fitz
import openai
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import ValidationError

from .llm import ask_llm, parse
from .ocr import ocr_model, pdf_analyze

# Переменные окружения (например, из docker compose) важнее, чем .env.
load_dotenv()
HOST = os.getenv("PACKING_HOST", "0.0.0.0")
PORT = int(os.getenv("PACKING_PORT", "8091"))
API_KEY = os.getenv("PACKING_API_KEY")
if not API_KEY:
    # Без ключа не стартуем: иначе сервис молча работал бы без защиты.
    raise RuntimeError("PACKING_API_KEY is not set")

# OCR нужен только сканам, но грузится при старте: иначе первый скан ждал бы загрузку моделей ~30 с.
ocr_model()
# PaddleOCR нельзя звать из нескольких потоков сразу, а FastAPI выполняет запросы в пуле потоков.
lock = threading.Lock()

app = FastAPI(title="erp-packing-service")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def check_api_key(key: str | None = Depends(api_key_header)):
    if key is None or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(401, "Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recognize", dependencies=[Depends(check_api_key)])
def recognize(file: UploadFile):
    try:
        with lock:
            document_text = pdf_analyze(file.file.read())
    except fitz.FileDataError:
        return JSONResponse({"error": "could not open pdf"}, status_code=422)
    try:
        content = ask_llm(document_text)
    except openai.APIError as e:
        return JSONResponse({"error": f"llm request failed: {e}"}, status_code=502)
    try:
        return parse(content)
    except ValidationError:
        return JSONResponse({"error": "llm returned invalid json", "llm_answer": content}, status_code=502)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
