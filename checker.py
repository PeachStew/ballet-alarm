import os
import json
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = "last_known.json"
BASE_URL = "https://www.korean-national-ballet.kr"
LIST_URL = f"{BASE_URL}/ko/news/notice/list"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def fetch_posts():
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    posts = []
    for a in soup.select(".section-notice a[href*='view']"):
        post_id = a["href"].split("id=")[-1]
        title_tag = a.select_one("strong.tit")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        url = f"{BASE_URL}/ko/news/notice/view?id={post_id}"
        posts.append({"id": post_id, "title": title, "url": url})

    return posts


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_ids": []}


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


def main():
    posts = fetch_posts()
    if not posts:
        print("게시글을 찾지 못했습니다.")
        return

    state = load_state()
    known_ids = set(state.get("known_ids", []))

    # 처음 실행 시: 현재 목록 저장만 하고 알림 없음
    if not known_ids:
        state["known_ids"] = [p["id"] for p in posts]
        save_state(state)
        print(f"초기화 완료. 현재 게시글 {len(posts)}개 저장.")
        return

    new_posts = [p for p in posts if p["id"] not in known_ids]

    if new_posts:
        for post in reversed(new_posts):  # 오래된 것부터 전송
            msg = (
                f"📢 <b>국립발레단 새 공지</b>\n\n"
                f"📌 {post['title']}\n"
                f"🔗 <a href=\"{post['url']}\">바로가기</a>"
            )
            send_telegram(msg)
            print(f"알림 전송: {post['title']}")

        # 전체 목록 갱신
        state["known_ids"] = [p["id"] for p in posts]
        save_state(state)
    else:
        print("새 게시글 없음.")


if __name__ == "__main__":
    main()
