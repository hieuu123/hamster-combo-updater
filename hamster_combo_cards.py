import base64
import requests
from bs4 import BeautifulSoup, NavigableString
import os

# ================= CONFIG =================
WP_URL = "https://blog.mexc.com/wp-json/wp/v2/posts"
WP_USERNAME = os.getenv("WP_USERNAME")   # username thật
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")   # app password thật
POST_ID = 296418  # ID bài Hamster Kombat Combo Cards
CHECK_TITLES = ["Gaming chairs", "Invite mentors", "FOCUS HELMETS"]  # Titles cũ để so sánh

# ================= SCRAPE =================
def scrape_combo():
    url = "https://hamster-combo.com/"
    print(f"[+] Scraping combo cards from {url}")
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    cards = soup.find_all("div", class_="hk-card", limit=3)
    if len(cards) < 3:
        raise RuntimeError("❌ Không tìm thấy đủ 3 .hk-card")

    titles, categories = [], []
    for card in cards:
        title_tag = card.find("p", class_="hk-title")
        cat_tag = card.find("p", class_="hk-category")
        if title_tag:
            titles.append(title_tag.get_text(strip=True))
        if cat_tag:
            categories.append(cat_tag.get_text(strip=True))

    print("[+] Scraped:")
    print("   Titles:", titles)
    print("   Categories:", categories)
    return titles, categories

# ================= FORMAT CATEGORY (in đậm) =================
def format_categories_bold(soup, categories):
    uniq = list(dict.fromkeys(categories))  # bỏ trùng, giữ thứ tự
    parts = []
    for i, cat in enumerate(uniq):
        strong = soup.new_tag("strong")
        strong.string = cat
        parts.append(strong)

    # ghép theo số lượng
    if len(parts) == 1:
        return ["Today’s combo focuses on the ", parts[0], " category"]
    elif len(parts) == 2:
        return ["Today’s combo focuses on the ", parts[0], " and ", parts[1], " category"]
    elif len(parts) == 3:
        return ["Today’s combo focuses on the ", parts[0], ", ", parts[1], " and ", parts[2], " category"]
    else:
        return ["Today’s combo focuses on the category"]

# ================= FETCH POST =================
def fetch_current_content():
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {"Authorization": f"Basic {token}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    url = f"{WP_URL}/{POST_ID}"
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"❌ Không lấy được post: {r.status_code} {r.text[:300]}")
    return r.json().get("content", {}).get("rendered", "")

# ================= UPDATE POST =================
def update_post(categories, titles, old_content):
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode("utf-8")
    headers = {"Authorization": f"Basic {token}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    soup = BeautifulSoup(old_content, "html.parser")

    # --- Tìm <p> chứa "Today’s combo focuses on..." ---
    p_tag = None
    for p in soup.find_all("p"):
        if "Today’s combo focuses on" in p.get_text():
            p_tag = p
            break
    if not p_tag:
        raise RuntimeError("❌ Không tìm thấy <p> Today’s combo focuses on...")

    # --- Thay text trước <strong> ---
    strong = p_tag.find("strong")
    if strong:
        for sib in list(p_tag.contents):
            if sib == strong:
                break
            sib.extract()

    # Clear toàn bộ <p>
    p_tag.clear()

    # Tạo câu mới có in đậm categories
    new_sentence_parts = format_categories_bold(soup, categories)
    for part in new_sentence_parts:
        if isinstance(part, str):
            p_tag.append(NavigableString(part))
        else:
            p_tag.append(part)

    # Thêm phần <strong> sẵn có (câu sau)
    trailing_strong = soup.new_tag("strong")
    trailing_strong.string = "Here are the three cards you need to collect or upgrade:"
    p_tag.append(". ")
    p_tag.append(trailing_strong)
    print("[+] Updated category sentence with bold categories")

    # --- Chèn thêm UL ngay sau <p> ---
    next_tag = p_tag.find_next_sibling()
    if next_tag and next_tag.name == "ul":
        print("⚠️ Đã có UL ngay sau <p> -> bỏ qua không chèn mới")
    else:
        new_ul = soup.new_tag("ul")
        new_ul["class"] = ["wp-block-list"]
        for t in titles:
            li = soup.new_tag("li")
            li.string = t
            new_ul.append(li)
        p_tag.insert_after(new_ul)
        print("[+] Inserted new UL with titles")

    new_content = str(soup)

    # --- Push update ---
    url_update = f"{WP_URL}/{POST_ID}"
    payload = {"content": new_content, "status": "publish"}
    up = requests.post(url_update, headers=headers, json=payload, timeout=20)
    print("🚀 Update status:", up.status_code)
    print("📄 Update response:", up.text[:300])
    if up.status_code == 200:
        print("✅ Post updated & published thành công!")

# ================= MAIN =================
if __name__ == "__main__":
    titles, categories = scrape_combo()

    if [t.strip() for t in titles] == [c.strip() for c in CHECK_TITLES]:
        print("⚠️ Titles scrape được trùng với CHECK_TITLES -> Không update")
    else:
        print("✅ Titles khác -> Update")
        old = fetch_current_content()
        update_post(categories, titles, old)
