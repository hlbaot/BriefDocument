# BriefDocument

## Chạy backend Python

```bash
cd /Users/baotoan/BriefDocument/BE
python3 -m pip install -r requirements.txt
python3 api_server.py
```

Backend mặc định chạy ở `http://127.0.0.1:8000`.

## Chạy frontend Next.js

```bash
cd /Users/baotoan/BriefDocument/FE
npm install
npm run dev
```

Frontend mặc định gọi backend qua biến `BACKEND_URL`.
Nếu không set gì thêm thì route Next.js sẽ dùng `http://127.0.0.1:8000`.

## 3 chế độ đầu vào

- `Text`: dán văn bản trực tiếp
- `Link`: gửi URL để backend scrape rồi tóm tắt
- `File`: tải `pdf`, `docx`, `txt`, `md`, `json`, `csv`

## Ghi chú

- `pdf` text-based đọc bằng `pypdf`
- `docx` đọc từ cấu trúc XML trong file Word
- `pdf` scan ảnh chưa có OCR
- `link` dùng pipeline hiện có trong `BE/text_summarize_v2.py`
