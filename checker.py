import os
import json
import warnings
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = "last_known.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

SITES = {
    "national": {
        "name": "국립발레단",
        "url": "https://www.korean-national-ballet.kr/ko/news/notice/list",
        "base_url": "https://www.korean-national-ballet.kr",
    },
    "universal": {
        "name": "유니버설발레단",
        "url": "https://www.universalballet.com/kr/bbs/board.php?bo_table=notice",
    },
}


def fetch_national_posts():
    site = SITES["national"]
    # 국립발레단 사이트는 비표준 SSL 인증서 사용으로 verify=False 필요
    resp = requests.get(site["url"], headers=HEADERS, timeout=15, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    posts = []
    for a in soup.select(".section-notice a[href*='view']"):
        post_id = a["href"].split("id=")[-1]
        title_tag = a.select_one("strong.tit")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        url = f"{site['base_url']}/ko/news/notice/view?id={post_id}"
        posts.append({"id": post_id, "title": title, "url": url})
    return posts


def fetch_universal_posts():
    site = SITES["universal"]
    resp = requests.get(site["url"], headers=HEADERS, timeout=15, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    posts = []
    for row in soup.select("#bo_list tbody tr"):
        a = row.select_one("td.td_subject a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a["href"]
        post_id = href.split("wr_id=")[-1]
        posts.append({"id": post_id, "title": title, "url": href})
    return posts


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def build_message(site_name, post):
    title = post["title"]
    url = post["url"]

    # 제목에 "티켓" 포함 시 클릭 가능한 하이퍼링크로 표시
    if "티켓" in title:
        title_line = f'🎟 <a href="{url}">{title}</a>'
        link_line = ""
    else:
        title_line = f"📌 {title}"
        link_line = f'\n🔗 <a href="{url}">바로가기</a>'

    return f"📢 <b>{site_name} 새 공지</b>\n\n{title_line}{link_line}"


def check_site(site_key, fetch_fn, state):
    """새 글이 있으면 True, 없으면 False 반환"""
    site_name = SITES[site_key]["name"]
    posts = fetch_fn()

    if not posts:
        print(f"[{site_name}] 게시글을 찾지 못했습니다.")
        return False

    known_ids = set(state.get(site_key, {}).get("known_ids", []))

    if not known_ids:
        state[site_key] = {"known_ids": [p["id"] for p in posts]}
        print(f"[{site_name}] 초기화 완료. {len(posts)}개 저장.")
        return False

    new_posts = [p for p in posts if p["id"] not in known_ids]

    if new_posts:
        for post in reversed(new_posts):
            msg = build_message(site_name, post)
            send_telegram(msg)
            print(f"[{site_name}] 알림 전송: {post['title']}")
        state[site_key] = {"known_ids": [p["id"] for p in posts]}
        return True

    print(f"[{site_name}] 새 게시글 없음.")
    return False


def main():
    state = load_state()

    found_new = False
    found_new |= check_site("national", fetch_national_posts, state)
    found_new |= check_site("universal", fetch_universal_posts, state)
    save_state(state)

    if not found_new:
        send_telegram("🔍 새로운 공지사항이 없습니다.")


if __name__ == "__main__":
    main()
