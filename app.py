from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path
import os, time
from sqlalchemy import text as sql_text

from .config import SECRET_KEY
from .db import SessionLocal, init_db, engine
from .models import Document, Page
from .ocr import render_pdf_to_images, ocr_image

BASE_DIR = Path(__file__).resolve().parents[0]
print(BASE_DIR)
DATA_DIR = BASE_DIR / "data"
DOC_DIR = DATA_DIR / "docs"
PAGE_DIR = DATA_DIR / "pages"
for d in (DATA_DIR, DOC_DIR, PAGE_DIR):
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}



def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app():
    app = Flask(__name__, static_folder=None)
    app.secret_key = SECRET_KEY
    init_db()

    CORS(app)

    @app.teardown_appcontext
    def remove_session(exc=None):
        SessionLocal.remove()

    @app.route("/api/recent", methods=['OPTIONS','GET'])
    def api_recent():
        if request.method == "OPTIONS":
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "*")
            response.headers.add('Access-Control-Allow-Methods', "*")
            return response
        print("test")
        sess = SessionLocal()
        try:
            rows = sess.execute(sql_text(
                "SELECT p.id, p.page_number, p.regular_image_path, p.ocr_text, d.filename "
                "FROM pages p JOIN documents d ON d.id = p.document_id "
                "ORDER BY p.id DESC LIMIT 50"
            )).all()
            total = sess.execute(sql_text("SELECT COUNT(*) FROM pages")).scalar_one()
            results = [{
                "id": r.id,
                "page_number": r.page_number,
                "filename": r.filename,
                "snippet": ((r.ocr_text or "")[:140]).replace("\n", " ")
            } for r in rows]
            return jsonify({"total": total, "results": results})
        finally:
            sess.close()

    @app.get("/api/search")
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"used_fulltext": False, "results": []})
        sess = SessionLocal()
        used_fulltext = False
        try:
            try:
                if engine.dialect.name == "mysql":
                    rows = sess.execute(sql_text(
                        "SELECT p.id, p.page_number, p.regular_image_path, d.filename, "
                        "SUBSTRING(p.ocr_text, GREATEST(1, LOCATE(:q, p.ocr_text) - 60), 160) as snippet, "
                        "LENGTH(p.ocr_text) - LENGTH(REPLACE(p.ocr_text, :q, '')) as number "
                        "FROM pages p JOIN documents d ON d.id=p.document_id "
                        "WHERE MATCH(p.ocr_text) AGAINST (:q IN NATURAL LANGUAGE MODE) "
                        "LIMIT 100"
                    ), {"q": q}).all()
                    used_fulltext = True
                else:
                    raise RuntimeError("Fallback")
            except Exception:
                like = f"%{q}%"
                rows = sess.execute(sql_text(
                    "SELECT p.id, p.page_number, p.regular_image_path, d.filename, "
                    "SUBSTRING(p.ocr_text, GREATEST(1, LOCATE(:q, p.ocr_text) - 60), 160) as snippet, "
                    "LENGTH(p.ocr_text) - LENGTH(REPLACE(p.ocr_text, :q, '')) as number "
                    "FROM pages p JOIN documents d ON d.id=p.document_id "
                    "WHERE p.ocr_text LIKE :like LIMIT 100"
                ), {"q": q, "like": like}).all()
            results = [{
                "id": r.id,
                "page_number": r.page_number,
                "filename": r.filename,
                "snippet": (r.snippet or "").replace("\n", " "),
                "number": r.number
            } for r in rows]
            return jsonify({"used_fulltext": used_fulltext, "results": results})
        finally:
            sess.close()

    @app.get("/api/list/documents")
    def api_list_documents():
        sess = SessionLocal()
        try:
            try:
                if engine.dialect.name == "mysql":
                    rows = sess.execute(sql_text(
                        "SELECT d.id, d.filename, d.uploaded_at, COUNT(p.id) as page_count FROM documents d "
                        "JOIN pages p on d.id=p.document_id GROUP BY d.id "
                        "LIMIT 100"
                    )).all()
                    used_fulltext = True
                else:
                    raise RuntimeError("Fallback")
            except Exception as e:
               print(e)

            results = [{
                "id": r.id,
                "filename": r.filename,
                "uploaded_at": r.uploaded_at,
                "page_count": r.page_count
            } for r in rows]
            return jsonify({"used_fulltext": used_fulltext, "results": results})
        finally:
            sess.close()

    @app.get("/api/page/<int:page_id>")
    def api_page_detail(page_id: int):
        sess = SessionLocal()
        try:
            row = sess.execute(sql_text(
                "SELECT p.id, p.page_number, p.regular_image_path, p.zoomed_image_path, p.ocr_text, d.filename "
                "FROM pages p JOIN documents d ON d.id=p.document_id WHERE p.id=:id"
            ), {"id": page_id}).first()
            if not row:
                return jsonify({"error": "Not found"}), 404
            return jsonify({
                "id": row.id,
                "page_number": row.page_number,
                "filename": row.filename,
                "ocr_text": row.ocr_text or "",
                "regular_image_url": f"/page-image/{row.id}",
                "zoomed_image_url": f"/page-zoom-image/{row.id}",

            })
        finally:
            sess.close()

    @app.get("/page-image/<int:page_id>")
    def page_image(page_id: int):
        sess = SessionLocal()
        try:
            path = sess.execute(sql_text("SELECT regular_image_path FROM pages WHERE id=:id"), {"id": page_id}).scalar()
        finally:
            sess.close()
        if not path:
            return ("Not found", 404)
        p = Path(path)
        return send_from_directory(directory=str(p.parent), path=p.name)

    @app.get("/page-zoom-image/<int:page_id>")
    def page_zoom_image(page_id: int):
        sess = SessionLocal()
        try:
            path = sess.execute(sql_text("SELECT zoomed_image_path FROM pages WHERE id=:id"), {"id": page_id}).scalar()
        finally:
            sess.close()
        if not path:
            return ("Not found", 404)
        p = Path(path)
        return send_from_directory(directory=str(p.parent), path=p.name)

    @app.route("/api/upload", methods=['POST','OPTIONS'])
    def api_upload():
        if request.method == "OPTIONS":
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "*")
            response.headers.add('Access-Control-Allow-Methods', "*")
            return response
        if request.method == 'POST':
            if "pdf" not in request.files:
                return jsonify({"error": "No file part named 'pdf'"}), 400
            f = request.files["pdf"]
            if f.filename == "":
                return jsonify({"error": "No selected file"}), 400
            if not allowed_file(f.filename):
                return jsonify({"error": "Only PDF files are allowed"}), 400

            filename = secure_filename(f.filename)
            pdf_path = DOC_DIR / filename
            print(pdf_path)
            base, ext = os.path.splitext(filename)
            counter = 1
            while pdf_path.exists():
                pdf_path = DOC_DIR / f"{base}_{counter}{ext}"
                counter += 1
            f.save(str(pdf_path))

            sess = SessionLocal()
            doc = Document(filename=pdf_path.name, stored_path=str(pdf_path))
            sess.add(doc); sess.commit()
            try:
                t0 = time.time()
                img_paths = render_pdf_to_images(pdf_path, PAGE_DIR)
                page_ids = []
                for i, img_path in enumerate(img_paths, start=1):
                    regular_image_path = str(img_path)[:-5] + "r.png"
                    text = ocr_image(img_path)
                    page = Page(document_id=doc.id, page_number=i, regular_image_path=str(regular_image_path),
                                zoomed_image_path=str(img_path), ocr_text=text)
                    sess.add(page); sess.flush(); page_ids.append(page.id)
                sess.commit()
                return jsonify({
                    "document_id": doc.id,
                    "pages_processed": len(page_ids),
                    "page_ids": page_ids,
                    "seconds": round(time.time() - t0, 2)
                })
            except Exception as e:
                print(str(e))
                sess.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                sess.close()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

