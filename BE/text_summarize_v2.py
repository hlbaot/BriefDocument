"""
Text Summarize v2 - Playwright + BeautifulSoup + AI Processing
==============================================================
Mục đích của file này:
- Nhận một URL bài viết hoặc trang web
- Dùng Playwright để mở trang và render JavaScript
- Dùng BeautifulSoup để lọc lấy nội dung chính
- Gửi nội dung cho Ollama để tóm tắt dạng Markdown

Cách dùng trong Jupyter Notebook:
    - Copy từng section vào các cell riêng
    - Hoặc import: from text_summarize_v2 import display_summary
"""

# ============================================================
# Cell 1: Imports & Auto-install
# ============================================================
import asyncio
import io
import json
import re
import subprocess
import sys
import zipfile
from xml.etree import ElementTree


def _auto_install(package_name: str, pip_name: str | None = None):
    """Thiếu thư viện nào thì tự cài thư viện đó."""
    install_name = pip_name or package_name
    print(f"📦 Đang tự động cài đặt {install_name}...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", install_name, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"✅ Đã cài đặt {install_name} thành công!")


# --- BeautifulSoup ---
try:
    from bs4 import BeautifulSoup, Comment  # type: ignore
except ImportError:
    _auto_install("bs4", "beautifulsoup4")
    from bs4 import BeautifulSoup, Comment  # type: ignore

# --- Ollama ---
try:
    import ollama  # type: ignore
except ImportError:
    _auto_install("ollama")
    import ollama  # type: ignore

# --- Playwright ---
try:
    from playwright.async_api import async_playwright  # type: ignore
except ImportError:
    _auto_install("playwright")
    # Cài browser Chromium cho Playwright
    print("🌐 Đang cài đặt Chromium browser cho Playwright...")
    subprocess.check_call(
        [sys.executable, "-m", "playwright", "install", "chromium"],
    )
    print("✅ Đã cài đặt Chromium thành công!")
    from playwright.async_api import async_playwright  # type: ignore

# --- IPython display (optional - chỉ dùng trong Jupyter) ---
try:
    from IPython.display import display, Markdown  # type: ignore
    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

# --- Requests (optional - dùng cho compare_scraping) ---
try:
    import requests as _requests_check  # type: ignore  # noqa: F401
    del _requests_check
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

MODEL = "llama3.2"
MAX_INPUT_CHARS = 12000


# ============================================================
# Cell 2: Website class - Playwright + BeautifulSoup
# ============================================================
class Website:
    """
    Lưu dữ liệu đã lấy được từ một trang web.

    Class này chịu trách nhiệm:
    - tải trang từ URL
    - trích xuất thông tin cơ bản
    - làm sạch HTML
    - giữ lại phần nội dung chính để đem đi tóm tắt
    """
    url: str
    title: str
    text: str
    meta_description: str
    author: str

    def __init__(self, url: str):
        self.url = url
        self.title = ""
        self.text = ""
        self.meta_description = ""
        self.author = ""

    async def _fetch(self):
        """
        Mở trang bằng Playwright để lấy HTML đã render xong JavaScript.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="vi-VN",
            )
            page = await context.new_page()

            try:
                # Mở trang và chờ mạng ổn định để nội dung tải xong hơn.
                await page.goto(self.url, wait_until="networkidle", timeout=30000)
                # Chờ thêm cho nội dung lazy-load nếu có.
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Playwright navigation warning: {e}")
                # Nếu cách chờ ở trên lỗi thì thử cách nhẹ hơn.
                try:
                    await page.goto(self.url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)
                except Exception as e2:
                    print(f"❌ Failed to load page: {e2}")
                    await browser.close()
                    self.title = "Failed to load"
                    self.text = f"Error loading {self.url}: {e2}"
                    return

            # Lấy HTML cuối cùng sau khi trang đã render.
            html_content = await page.content()
            await browser.close()

        # Chuyển HTML sang bước làm sạch và trích xuất nội dung.
        self._parse_html(html_content)

    def _parse_html(self, html: str):
        """
        Dùng BeautifulSoup để bỏ phần thừa và lấy nội dung chính.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Lấy tiêu đề của trang.
        self.title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"

        # Lấy mô tả ngắn của trang nếu có.
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            self.meta_description = meta_desc["content"].strip()

        # Nếu thiếu description thường thì lấy từ Open Graph.
        if not self.meta_description:
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            if og_desc and og_desc.get("content"):
                self.meta_description = og_desc["content"].strip()

        # Lấy tên tác giả nếu trang có khai báo.
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            self.author = meta_author["content"].strip()

        # Nếu trang không có body thì không có nội dung để xử lý.
        if not soup.body:
            self.text = "No body content found"
            return

        body = soup.body

        # Xóa các thẻ không cần cho phần tóm tắt.
        tags_to_remove = [
            "script", "style", "img", "input", "textarea", "select",
            "button", "iframe", "noscript", "svg", "canvas", "video",
            "audio", "source", "picture", "map", "object", "embed",
            "form",
        ]
        for tag_name in tags_to_remove:
            for tag in body.find_all(tag_name):
                tag.decompose()

        # Xóa comment trong HTML.
        for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Xóa các vùng như menu, header, footer, sidebar.
        nav_tags = ["nav", "header", "footer", "aside"]
        for tag_name in nav_tags:
            for tag in body.find_all(tag_name):
                tag.decompose()

        # Xóa thêm các khối có class/id giống quảng cáo, popup, comment...
        noise_patterns = re.compile(
            r"(nav|menu|sidebar|footer|header|cookie|popup|banner|"
            r"advertisement|ad-|ads-|social|share|comment|related|"
            r"breadcrumb|pagination|widget|modal|overlay|toast|"
            r"newsletter|subscribe|signup)",
            re.IGNORECASE,
        )

        for tag in body.find_all(True):
            # Bỏ qua phần tử đã bị xóa trước đó.
            if tag.attrs is None:
                continue
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "") or ""
            if noise_patterns.search(classes) or noise_patterns.search(tag_id):
                tag.decompose()

        # Cố gắng tìm đúng vùng nội dung chính.
        main_content = None

        # Ưu tiên lấy trong article hoặc main.
        main_content = body.find("article") or body.find("main")

        # Nếu chưa thấy thì tìm theo class/id phổ biến.
        if not main_content:
            content_patterns = [
                {"class_": re.compile(r"(article|post|entry|content|story|body-text)", re.I)},
                {"id": re.compile(r"(article|post|entry|content|story|main)", re.I)},
                {"role": "main"},
            ]
            for pattern in content_patterns:
                main_content = body.find("div", **pattern)
                if main_content:
                    break

        # Không tìm được thì dùng toàn bộ body đã làm sạch.
        source = main_content if main_content else body

        # Đổi HTML thành text.
        text = source.get_text(separator="\n", strip=True)

        # Dọn dòng rỗng và khoảng trắng dư.
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 1:  # Bỏ các dòng quá ngắn.
                cleaned_lines.append(line)

        # Bỏ các dòng trùng nhau liên tiếp.
        final_lines = []
        for line in cleaned_lines:
            if not final_lines or line != final_lines[-1]:
                final_lines.append(line)

        self.text = "\n".join(final_lines)

        # Giới hạn độ dài để tránh gửi quá nhiều token cho model.
        max_chars = 8000
        if len(self.text) > max_chars:
            self.text = self.text[:max_chars] + "\n\n[... nội dung bị cắt bớt ...]"

    @classmethod
    async def create(cls, url: str) -> "Website":
        """
        Tạo Website object và tự chạy bước lấy dữ liệu.
        """
        instance = cls(url)
        await instance._fetch()
        return instance


# ============================================================
# Cell 3: AI Processing - Enhanced Prompts
# ============================================================

system_prompt = """You are an expert content analyst assistant. Your task is to analyze the contents of a website and provide a clear, well-structured summary.

Rules:
1. IGNORE navigation menus, footers, sidebars, ads, cookie notices, and other non-content elements.
2. Focus on the MAIN CONTENT of the page (articles, news, product descriptions, etc.).
3. If the content is in Vietnamese, respond in Vietnamese.
4. If the content is in English, respond in English.
5. Structure your response with clear headings and bullet points.
6. If there are news articles or announcements, summarize key points with dates if available.
7. Keep the summary concise but comprehensive.
8. Respond in Markdown format."""


def user_prompt_for(website: Website) -> str:
    """
    Tạo prompt gửi cho AI từ dữ liệu đã trích xuất.
    """
    prompt_parts = [
        f"# Website Analysis Request\n",
        f"**URL:** {website.url}\n",
        f"**Title:** {website.title}\n",
    ]

    if website.meta_description:
        prompt_parts.append(f"**Description:** {website.meta_description}\n")

    if website.author:
        prompt_parts.append(f"**Author:** {website.author}\n")

    prompt_parts.append(
        "\n## Instructions\n"
        "Please analyze this website's content and provide:\n"
        "1. A brief overview of what this page is about\n"
        "2. Key information and main points\n"
        "3. Any news, announcements, or important updates\n"
        "4. A conclusion or takeaway\n\n"
    )

    prompt_parts.append(f"## Page Content\n\n{website.text}")

    return "\n".join(prompt_parts)


def messages_for(website: Website) -> list:
    """Đóng gói prompt theo định dạng Ollama chat."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt_for(website)},
    ]


# ============================================================
# Cell 4: Summarize functions
# ============================================================

text_system_prompt = """You are an expert assistant for summarizing user-provided content.

Rules:
1. Respond in Vietnamese unless the user content is clearly in another language.
2. Keep the answer easy to scan.
3. Use simple Markdown headings and bullet points.
4. Focus on the main ideas, decisions, and next actions.
5. If the content is too short, just answer directly.
"""


def _truncate_text(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Giới hạn độ dài text trước khi gửi cho model."""
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars] + "\n\n[... nội dung bị cắt bớt ...]"


def text_messages_for(text: str, source_label: str = "Văn bản người dùng") -> list:
    """Tạo messages cho trường hợp người dùng gửi text hoặc file."""
    prompt = (
        f"# Nguồn nội dung\n"
        f"- Loại: {source_label}\n\n"
        f"# Nội dung cần tóm tắt\n\n{_truncate_text(text)}"
    )
    return [
        {"role": "system", "content": text_system_prompt},
        {"role": "user", "content": prompt},
    ]


async def summarize_text(text: str, source_label: str = "Văn bản người dùng") -> str:
    """Tóm tắt text thô bằng Ollama."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Không có nội dung để tóm tắt.")

    messages = text_messages_for(cleaned, source_label=source_label)
    response = await asyncio.to_thread(ollama.chat, model=MODEL, messages=messages)
    return response["message"]["content"]


def extract_text_from_plain_bytes(file_bytes: bytes, filename: str) -> str:
    """Đọc các file text cơ bản."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension == "json":
        parsed = json.loads(file_bytes.decode("utf-8"))
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    return file_bytes.decode("utf-8", errors="replace")


def extract_text_from_docx_bytes(file_bytes: bytes) -> str:
    """Đọc DOCX bằng cấu trúc zip/xml chuẩn của Word."""
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        document = archive.read("word/document.xml")

    root = ElementTree.fromstring(document)
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:p", namespaces):
        texts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespaces)
        ]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)

    return "\n".join(paragraphs)


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Đọc PDF bằng pypdf nếu thư viện có sẵn hoặc cài được."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        _auto_install("pypdf")
        from pypdf import PdfReader  # type: ignore

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []

    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())

    return "\n\n".join(part for part in pages if part)


def extract_text_from_file_bytes(file_bytes: bytes, filename: str) -> str:
    """Chọn cách đọc nội dung dựa trên đuôi file."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension in {"txt", "md", "markdown", "csv", "json"}:
        return extract_text_from_plain_bytes(file_bytes, filename)

    if extension == "docx":
        return extract_text_from_docx_bytes(file_bytes)

    if extension == "pdf":
        return extract_text_from_pdf_bytes(file_bytes)

    raise ValueError(f"Chưa hỗ trợ loại file: .{extension or 'unknown'}")


async def summarize(url: str) -> str:
    """
    Hàm chính để:
    - lấy nội dung trang
    - làm sạch nội dung
    - gửi cho AI để tóm tắt
    """
    print(f"🌐 Đang tải trang bằng Playwright: {url}")
    website = await Website.create(url)

    print(f"📄 Title: {website.title}")
    if website.meta_description:
        desc_preview: str = str(website.meta_description[:100])
        print(f"📝 Description: {desc_preview}...")
    print(f"📊 Nội dung: {len(website.text)} ký tự")
    print(f"🤖 Đang gửi cho AI ({MODEL}) phân tích...\n")

    if not website.text.strip():
        raise ValueError("Không lấy được nội dung từ URL.")

    messages = messages_for(website)
    response = await asyncio.to_thread(ollama.chat, model=MODEL, messages=messages)
    return response["message"]["content"]


async def display_summary(url: str):
    """
    Hiển thị bản tóm tắt ra màn hình.
    Trong Jupyter sẽ render Markdown, ngoài terminal thì print thường.
    """
    summary = await summarize(url)
    if HAS_IPYTHON:
        display(Markdown(summary))
    else:
        print(summary)


# ============================================================
# Cell 5: Helper - Compare old vs new scraping
# ============================================================

async def compare_scraping(url: str):
    """
    So sánh lượng nội dung lấy được giữa cách cũ và cách mới.
    """
    if not HAS_REQUESTS:
        _auto_install("requests")
    import requests as req  # type: ignore

    print("=" * 60)
    print("📊 SO SÁNH: requests vs Playwright")
    print("=" * 60)

    # Cách cũ: chỉ tải HTML tĩnh.
    print("\n--- 🔴 Phương pháp cũ: requests (HTML tĩnh) ---")
    old_text = ""
    try:
        response = req.get(url, timeout=10)
        soup_old = BeautifulSoup(response.content, "html.parser")
        old_title = soup_old.title.string if soup_old.title else "No title"
        if soup_old.body:
            for tag in soup_old.body(["script", "style", "img", "input"]):
                tag.decompose()
            old_text = soup_old.body.get_text(separator="\n", strip=True)
        print(f"  Title: {old_title}")
        print(f"  Nội dung: {len(old_text)} ký tự")
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")

    # Cách mới: mở bằng browser để render JavaScript.
    print("\n--- 🟢 Phương pháp mới: Playwright (render JS) ---")
    website = await Website.create(url)
    print(f"  Title: {website.title}")
    if website.meta_description:
        desc_str: str = str(website.meta_description[:100])
        print(f"  Description: {desc_str}")
    else:
        print("  Description: N/A")
    print(f"  Nội dung: {len(website.text)} ký tự")

    # So sánh chênh lệch nội dung giữa 2 cách.
    if old_text:
        diff = len(website.text) - len(old_text)
        print(f"\n📈 Chênh lệch nội dung: {diff:+d} ký tự")
        if diff > 0:
            print("   → Playwright lấy được NHIỀU nội dung hơn (JS-rendered content)")
        elif diff < 0:
            print("   → Playwright lấy ít hơn nhưng SẠCH hơn (đã lọc noise)")
        else:
            print("   → Tương đương")

    print("\n" + "=" * 60)


# ============================================================
# Cell 6: Run (dùng trong Jupyter hoặc command line)
# ============================================================

# Ví dụ dùng trong Jupyter Notebook.
# Chạy cell này trong Jupyter:
#
#   await display_summary("https://www.vietnamplus.vn/tong-bi-thu-chu-tri-hop-thuong-truc-ban-chi-dao-ve-phat-trien-khoa-hoc-cong-nghe-post1098519.vnp")
#
# Hoặc so sánh:
#   await compare_scraping("https://anthropic.com")


# Ví dụ chạy trực tiếp từ command line.
if __name__ == "__main__":
    test_urls = [
        "https://anthropic.com",
        "https://www.vietnamplus.vn/tong-bi-thu-chu-tri-hop-thuong-truc-ban-chi-dao-ve-phat-trien-khoa-hoc-cong-nghe-post1098519.vnp",
    ]
    url = test_urls[0]
    print(f"\n🚀 Testing with: {url}\n")
    result = asyncio.run(summarize(url))
    print(result)
