import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .ocr import pdf_analyze

class Item(BaseModel):
    name: str | None
    quantity: str | None
    quantity_unit: str | None
    package_type: str | None
    package_count: str | None

class PackingList(BaseModel):
    items: list[Item]
    total_packages: str | None

load_dotenv()
client = OpenAI(base_url=os.getenv("LLM_URL", "http://100.126.177.30:11434/v1"), api_key="not-needed")
MODEL = os.getenv("LLM_MODEL", "qwen3.5:9b")

SYSTEM = """Ты извлекаешь данные из упаковочных листов (packing list).
quantity — количество товара (km, pcs, kg); package_count — число упаковок (carton, box, pallet, case).
Числа переписывай ровно как в документе. Если упаковка общая для нескольких строк, укажи её у первой.
Если значения нет — null, ничего не придумывай.
Ответ — только JSON такого вида:
{"items": [{"name": "...", "quantity": "...", "quantity_unit": "...", "package_type": "...", "package_count": "..."}], "total_packages": "..."}"""


def ask_llm(document_text):
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        reasoning_effort="none",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": document_text},
        ],
    )
    return resp.choices[0].message.content


def parse(content):
    content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return PackingList.model_validate_json(content)

if __name__ == "__main__":
    OUTPUT_DIR = Path("output")
    OUTPUT_DIR.mkdir(exist_ok=True)

    for pdf_path in Path("packing-lists").glob("*.pdf"):
        print(pdf_path.name)
        content = ask_llm(pdf_analyze(pdf_path))
        try:
            data = parse(content)
            (OUTPUT_DIR / f"{pdf_path.stem}.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
        except ValidationError:
            (OUTPUT_DIR / f"{pdf_path.stem}.error.txt").write_text(content, encoding="utf-8")
