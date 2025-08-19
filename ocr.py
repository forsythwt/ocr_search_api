import re
import pathlib
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from .config import TESSERACT_CMD

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def render_pdf_to_images(pdf_path: pathlib.Path, out_dir: pathlib.Path):
    paths = []
    try:
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc, start=1):
                zoom = 5.0
                regular_pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
                zoomed_pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                out_dir.mkdir(parents=True, exist_ok=True)
                regular_out_path = out_dir / f"{pdf_path.stem}_p{i:03d}_r.png"
                zoomed_out_path = out_dir / f"{pdf_path.stem}_p{i:03d}_z.png"
                regular_pix.save(str(regular_out_path))
                zoomed_pix.save(str(zoomed_out_path))
                paths.append(zoomed_out_path)
        return paths

    except Exception as e:
        print("Exception processing pages {}".format(str(e)))
def ocr_image(image_path: pathlib.Path) -> str:
    with Image.open(image_path) as im:
        im = im.convert("L")
        text = pytesseract.image_to_string(im, lang="eng")
    return re.sub(r"\s+", " ", text).strip()