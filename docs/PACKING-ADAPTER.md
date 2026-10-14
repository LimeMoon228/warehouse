# Packing-сервис: контракт веб-адаптера

Сервис принимает PDF упаковочного листа (packing list) и возвращает JSON: товары, их количество, тип и число упаковок.

## Схема

```
ERP-бек ──POST /recognize (PDF)──► packing-сервис ──текст──► LLM (Ollama, qwen3.5:9b)
        ◄──────────── JSON ────────┘               ◄─JSON─┘
```

- Есть текстовый слой (почти все PDF) — текст и таблицы берутся из него через PyMuPDF.
- Нет текстового слоя (скан) — таблица читается PaddleOCR.
- Разбор по полям делает LLM; сервис проверяет, что ответ — JSON нужного вида.

Обрабатывается только первая страница. PDF обрабатывается в памяти и нигде не сохраняется.

## Эндпоинты

### `POST /recognize`

**Запрос** — `multipart/form-data`, часть `file` с байтами PDF, заголовок `X-API-Key`.

**Ответ `200`** — `application/json`:

```json
{
  "items": [
    { "name": "Composite Square Tube", "quantity": "69200", "quantity_unit": "pcs", "package_type": "pallets", "package_count": "5" },
    { "name": "Composite Square Tube", "quantity": "34600", "quantity_unit": "pcs", "package_type": null, "package_count": null }
  ],
  "total_packages": "5"
}
```

| Поле | Тип | Правило |
|---|---|---|
| `items[].name` | string \| null | название товара; `null`, если оно в объединённой ячейке с предыдущей строкой |
| `items[].quantity` | string \| null | количество товара **как в документе** (`"1597,041"`, `"26,365.58"`) — числом не приводится |
| `items[].quantity_unit` | string \| null | единица: km, pcs, kg… |
| `items[].package_type` | string \| null | carton, box, pallet, case… |
| `items[].package_count` | string \| null | число упаковок; если упаковка общая для нескольких строк — только у первой |
| `total_packages` | string \| null | итог упаковок по документу |

Ответ LLM не проверяется на правильность по смыслу: числа могут оказаться не в том поле. Перед использованием
стоит сверять с документом.

**Ошибки** — тело `{"error": "..."}`:

| Статус | Когда |
|---|---|
| `401` | нет `X-API-Key` или он неверный |
| `422` | файл — не PDF или пустой |
| `502` | LLM недоступна или вернула не тот JSON (сырой ответ — в `llm_answer`) |
| `500` | упал OCR (например, скан пустой страницы) |

### `GET /health`

`200`, когда модели OCR загружены и сервис готов принимать файлы. Доступность LLM не проверяет.

## Время ответа

- PDF с текстовым слоем — ~3 с (почти всё время — ответ LLM).
- Скан — плюс время OCR (на GPU — секунды, на CPU — около минуты).
- Модели OCR грузятся один раз при старте (~30 с). Каждый воркер `uvicorn` держит свою копию.

## Настройки

Переменные окружения или `.env` в корне проекта (переменные окружения важнее):

| Переменная | По умолчанию | Что это |
|---|---|---|
| `PACKING_API_KEY` | — | ключ для `X-API-Key`; без него сервис не стартует |
| `PACKING_HOST` | `0.0.0.0` | |
| `PACKING_PORT` | `8091` | |
| `LLM_URL` | `http://100.126.177.30:11434/v1` | OpenAI-совместимый адрес Ollama |
| `LLM_MODEL` | `qwen3.5:9b` | |
| `OCR_DEVICE` | авто | `gpu:0` или `cpu`; без него paddle берёт GPU, если она есть |

## Запуск

```bash
python -m packing_service.api                 # сервис
python -m packing_service.llm                 # как раньше: вся папка packing-lists → output/*.json
python -m packing_service.ocr file.pdf        # только текст документа, без LLM
```

Docker-образ — с весами OCR внутри. LLM в образ не входит: контейнеру нужен доступ к `LLM_URL`
(адрес `100.126.177.30` — в сети Tailscale).

## Проверка

```bash
curl -H "X-API-Key: $PACKING_API_KEY" -F "file=@packing.pdf;type=application/pdf" http://localhost:8091/recognize
curl -i http://localhost:8091/health
```
