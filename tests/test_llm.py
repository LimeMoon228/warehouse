import pytest
from pydantic import ValidationError

from packing_service.llm import parse

# Ответ qwen3.5:9b на PL-SEGU5606319: упаковка в объединённой ячейке — только у первой строки
ANSWER = """```json
{"items": [
  {"name": "Composite Square Tube", "quantity": 69200, "quantity_unit": "pcs", "package_type": "pallets", "package_count": 5},
  {"name": "Composite Square Tube", "quantity": 34600, "quantity_unit": "pcs", "package_type": null, "package_count": null}
], "total_packages": 5}
```"""


def test_fenced_answer():
    data = parse(ANSWER)
    assert data.items[0].quantity == 69200
    assert data.items[0].package_count == "5"  # числа в строковых полях становятся строками
    assert data.items[1].package_type is None
    assert data.total_packages == "5"


def test_quantity_is_number_unit_and_package_upper():
    data = parse('{"items": [{"name": "OPTICAL FIBER G657 A2", "quantity": 1597.041, "quantity_unit": "km", "package_type": "Carton", "package_count": "9"}], "total_packages": "9"}')
    assert data.items[0].quantity == 1597.041
    assert data.items[0].quantity_unit == "KM"
    assert data.items[0].package_type == "CARTON"


def test_quantity_with_comma_is_error():
    # Перевод "1597,041" в число — работа модели; угадывать, запятая это или разделитель тысяч, код не должен
    with pytest.raises(ValidationError):
        parse('{"items": [{"name": "x", "quantity": "1597,041", "quantity_unit": "km", "package_type": null, "package_count": null}], "total_packages": null}')


def test_plain_answer_same_as_fenced():
    plain = ANSWER.removeprefix("```json").removesuffix("```")
    assert parse(plain) == parse(ANSWER)


def test_name_may_be_null():
    # Название в объединённой ячейке модель отдаёт как null — документ не должен из-за этого отбрасываться
    data = parse('{"items": [{"name": null, "quantity": 2, "quantity_unit": null, "package_type": "case", "package_count": "2"}], "total_packages": "2"}')
    assert data.items[0].name is None


def test_schema_echo_is_error():
    # Так модель иногда отвечала, когда в инструкции была JSON-схема
    with pytest.raises(ValidationError):
        parse('{"$defs": {"Item": {}}, "required": ["items", "total_packages"], "type": "object"}')
