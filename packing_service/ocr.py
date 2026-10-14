from functools import cache
import os
import sys

import fitz
import cv2
from paddleocr import TableRecognitionPipelineV2
import numpy as np
@cache
def ocr_model():
    ocr = TableRecognitionPipelineV2(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_layout_detection=False,
        text_det_limit_type="min",
        text_det_limit_side_len=736,
        device=os.getenv("OCR_DEVICE"),
        text_recognition_batch_size=16,
    )
    return ocr

def pdf_analyze(pdf):
    doc = fitz.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else fitz.open(pdf)
    text = doc[0].get_text()

    if text.strip():
        tables = [t.to_markdown(fill_empty=False) for t in doc[0].find_tables()]
        document_text = text + "\n\n" + "\n\n".join(tables)
    else:
        pix = doc[0].get_pixmap(dpi=400)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        bw = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,cv2.THRESH_BINARY, 15, -2)
        h_len = image.shape[1] // 30
        v_len = image.shape[0] // 30
        horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1)))
        vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len)))
        grid = cv2.add(horiz, vert)
        grid = cv2.dilate(grid, np.ones((5, 5), np.uint8), iterations=2)

        contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[2] * cv2.boundingRect(c)[3],reverse=True)
        x, y, w, h = cv2.boundingRect(contours[0])
        crop = image[y:y + h, x:x + w]

        res = ocr_model().predict(crop)[0]
        document_text = res.html["table_1"]

    return document_text

if __name__ == "__main__":
    print(pdf_analyze(sys.argv[1]))
