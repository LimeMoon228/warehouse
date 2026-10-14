import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .ocr import pdf_analyze

class Item(BaseModel):
    # С английским промптом модель отдаёт package_count числом — в строковых полях принимаем и числа
    model_config = ConfigDict(coerce_numbers_to_str=True)

    name: str | None
    quantity: int | float | None
    quantity_unit: str | None
    package_type: str | None
    package_count: str | None

    @field_validator("quantity_unit", "package_type")
    @classmethod
    def upper(cls, v):
        return v.upper() if v else v

class PackingList(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    items: list[Item]
    total_packages: str | None

load_dotenv()
client = OpenAI(base_url=os.getenv("LLM_URL", "http://100.126.177.30:11434/v1"), api_key="not-needed")
MODEL = os.getenv("LLM_MODEL", "qwen3.5:9b")

SYSTEM = """You extract data from packing lists.
quantity is the amount of goods (km, pcs, kg); package_count is the number of packages (carton, box, pallet, case).
quantity must be a JSON number: use a dot as the decimal separator, drop thousands separators and units (e.g. "1597,041" -> 1597.041, "26,365.58" -> 26365.58).
Copy other values exactly as in the document. If a package is shared by several rows, put it on the first row only.
If a value is missing, use null; do not invent anything.
Answer with JSON only, in this form:
{"items": [{"name": "...", "quantity": <number>, "quantity_unit": "...", "package_type": "...", "package_count": "..."}], "total_packages": "..."}"""


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
