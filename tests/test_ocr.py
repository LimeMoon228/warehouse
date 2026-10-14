import fitz

from packing_service.ocr import pdf_analyze


def make_pdf():
    # PDF с текстовым слоем и таблицей 3x2; ячейка Q'TY во второй строке пустая, как объединённая
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 40), "PACKING LIST")
    for x in (50, 200, 350, 500):
        page.draw_line((x, 60), (x, 140))
    for y in (60, 100, 140):
        page.draw_line((50, y), (500, y))
    for i, t in enumerate(["NAME", "Quantity", "Q'TY"]):
        page.insert_text((60 + 150 * i, 85), t)
    for i, t in enumerate(["Composite Square Tube", "69200"]):
        page.insert_text((60 + 150 * i, 125), t)
    return doc.tobytes()


def test_text_layer_from_bytes():
    text = pdf_analyze(make_pdf())
    assert "PACKING LIST" in text
    assert "|Composite Square Tube|69200||" in text  # пустая ячейка не заполнена соседним значением


def test_text_layer_from_path(tmp_path):
    path = tmp_path / "packing.pdf"
    path.write_bytes(make_pdf())
    assert pdf_analyze(path) == pdf_analyze(make_pdf())
