"""
Backend API cho BriefDocument.

Hỗ trợ 3 chế độ:
- text: tóm tắt văn bản người dùng dán vào
- link: lấy nội dung từ URL rồi tóm tắt
- file: đọc file từ máy rồi tóm tắt
"""

import asyncio
import sys
from typing import Any


def _auto_install(package_name: str, pip_name: str | None = None):
    """Thiếu thư viện nào thì tự cài thư viện đó."""
    import subprocess

    install_name = pip_name or package_name
    subprocess.check_call([sys.executable, "-m", "pip", "install", install_name, "-q"])


try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    _auto_install("fastapi")
    _auto_install("uvicorn")
    _auto_install("python-multipart")
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.middleware.cors import CORSMiddleware

from text_summarize_v2 import extract_text_from_file_bytes, summarize, summarize_text

app = FastAPI(title="BriefDocument API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ok(summary: str, input_type: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "inputType": input_type,
        "summary": summary,
        "meta": meta or {},
    }


def _error(message: str, input_type: str, status_code: int = 400) -> tuple[dict[str, Any], int]:
    return (
        {
            "ok": False,
            "inputType": input_type,
            "error": message,
        },
        status_code,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/summarize/text")
async def summarize_text_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    if not text:
        error, status = _error("Thiếu nội dung text.", "text")
        from fastapi import HTTPException
        raise HTTPException(status_code=status, detail=error["error"])

    source_label = str(payload.get("sourceLabel", "Văn bản người dùng"))
    summary = await summarize_text(text, source_label=source_label)
    return _ok(summary, "text", {"sourceLabel": source_label, "chars": len(text)})


@app.post("/summarize/link")
async def summarize_link_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    if not url:
        error, status = _error("Thiếu URL.", "link")
        from fastapi import HTTPException
        raise HTTPException(status_code=status, detail=error["error"])

    summary = await summarize(url)
    return _ok(summary, "link", {"url": url})


@app.post("/summarize/file")
async def summarize_file_endpoint(
    file: UploadFile = File(...),
    source_label: str = Form("Tệp người dùng"),
) -> dict[str, Any]:
    if not file.filename:
        error, status = _error("Thiếu tên file.", "file")
        from fastapi import HTTPException
        raise HTTPException(status_code=status, detail=error["error"])

    file_bytes = await file.read()
    if not file_bytes:
        error, status = _error("File rỗng.", "file")
        from fastapi import HTTPException
        raise HTTPException(status_code=status, detail=error["error"])

    text = await asyncio.to_thread(extract_text_from_file_bytes, file_bytes, file.filename)
    if not text.strip():
        error, status = _error("Không đọc được nội dung file.", "file")
        from fastapi import HTTPException
        raise HTTPException(status_code=status, detail=error["error"])

    summary = await summarize_text(text, source_label=f"{source_label}: {file.filename}")
    return _ok(
        summary,
        "file",
        {
            "fileName": file.filename,
            "chars": len(text),
        },
    )


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        _auto_install("uvicorn")
        import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
