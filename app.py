import sqlite3
from flask import Flask, render_template, request
import requests
import json
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# 네이버 API 인증 정보
CLIENT_ID = "m6nZpyW187lm1c7iMKSH"
CLIENT_SECRET = "6yXrem4rjM"

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
DB_PATH = "naverblog.db"


def init_db():
    """처음 실행할 때 검색어/멜론 차트 테이블 없으면 만들어 줌"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 검색어 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_keyword (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            count INTEGER DEFAULT 1,
            last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 멜론 차트 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS melon_chart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rank INTEGER,
            title TEXT,
            artist TEXT
        );
    """)

    conn.commit()
    conn.close()



def save_search_keyword(keyword: str):
    """검색어를 DB에 저장하거나 count 올리기"""
    if not keyword:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO search_keyword (keyword, count)
        VALUES (?, 1)
        ON CONFLICT(keyword) DO UPDATE SET
            count = count + 1,
            last_searched = CURRENT_TIMESTAMP;
    """, (keyword,))
    conn.commit()
    conn.close()


db_initialized = False


def get_melon_top100():
    url = "https://www.melon.com/chart/index.htm"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=5)

        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("tr.lst50") + soup.select("tr.lst100")

        if not rows:
            return None  # 멜론이 페이지 차단한 상황

        songs = []
        for row in rows:
            rank = row.select_one("span.rank").get_text(strip=True)
            title = row.select_one("div.ellipsis.rank01 a").get_text(strip=True)
            artist = row.select_one("div.ellipsis.rank02 a").get_text(strip=True)
            songs.append({"rank": rank, "title": title, "artist": artist})

        return songs

    except Exception:
        return None



def save_melon_chart_to_db(songs):
    """멜론 차트 전체를 DB에 덮어쓰기 저장"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 기존 차트 싹 지우고
    cur.execute("DELETE FROM melon_chart")

    # 새 차트 저장
    for s in songs:
        cur.execute(
            "INSERT INTO melon_chart (rank, title, artist) VALUES (?, ?, ?)",
            (int(s["rank"]), s["title"], s["artist"])
        )

    conn.commit()
    conn.close()


def load_melon_chart_from_db():
    """DB에 저장된 멜론 차트 불러오기 (리스트[dict])"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT rank, title, artist FROM melon_chart ORDER BY rank ASC")
    rows = cur.fetchall()
    conn.close()

    songs = []
    for rank, title, artist in rows:
        songs.append({
            "rank": rank,
            "title": title,
            "artist": artist
        })
    return songs


def search_artist_in_chart(artist_name: str):
    """가수 이름으로 멜론 차트에서 곡 검색"""
    if not artist_name:
        return []

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT rank, title, artist
        FROM melon_chart
        WHERE artist LIKE ?
        ORDER BY rank ASC
    """, (f"%{artist_name}%",))
    rows = cur.fetchall()
    conn.close()

    results = []
    for rank, title, artist in rows:
        results.append({
            "rank": rank,
            "title": title,
            "artist": artist
        })
    return results

def get_artist_song_count_ranking():
    """가수별 TOP100 내 곡 수 랭킹"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT artist, COUNT(*) as song_count
        FROM melon_chart
        GROUP BY artist
        ORDER BY song_count DESC, artist ASC
    """)
    rows = cur.fetchall()
    conn.close()

    ranking = []
    for artist, count in rows:
        ranking.append({
            "artist": artist,
            "count": count
        })
    return ranking


@app.before_request
def before_request():
    global db_initialized
    if not db_initialized:
        init_db()
        db_initialized = True

@app.route('/blog', methods=['GET', 'POST'])
def search_blog():
    search_results = None
    if request.method == 'POST':
        query = request.form.get('query')

        if query:
            # ✅ 검색어를 sqlite에 저장
            save_search_keyword(query)

            headers = {
                "X-Naver-Client-Id": CLIENT_ID,
                "X-Naver-Client-Secret": CLIENT_SECRET
            }
            params = {
                "query": query,
                "display": 20,
                "sort": "sim"
            }
            response = requests.get(NAVER_API_URL, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                search_results = data.get('items')
            else:
                print(f"Error: {response.status_code}, {response.text}")

    return render_template('index.html', search_results=search_results)


@app.route('/rank')
def rank():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT keyword, count
        FROM search_keyword
        ORDER BY count DESC, last_searched DESC
        LIMIT 20;
    """)
    rows = cur.fetchall()
    conn.close()

    return render_template('rank.html', rankings=rows)


@app.route('/')
def home():
    return render_template('main.html')

@app.route("/melon")
def melon_chart():
    songs = get_melon_top100()

    # 크롤링 실패하면 DB에서 불러오기
    if not songs:
        songs = load_melon_chart_from_db()

    return render_template("melon.html", songs=songs, artist_songs=None, artist_name=None)


@app.route("/melon/artist", methods=["POST"])
def melon_artist():
    artist_name = request.form.get("artist", "").strip()

    # DB에서 현재 저장된 차트 불러오기
    songs = load_melon_chart_from_db()
    # 가수 이름으로 검색
    artist_songs = search_artist_in_chart(artist_name)

    return render_template(
        "melon.html",
        songs=songs,
        artist_songs=artist_songs,
        artist_name=artist_name
    )


@app.route("/test")
def test():
    url = "https://m2.melon.com/m6/chart/realTime/new/today.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)

    return res.text

@app.route("/melon/artist-rank")
def melon_artist_rank():
    ranking = get_artist_song_count_ranking()
    return render_template("melon_artist_rank.html", ranking=ranking)




if __name__ == '__main__':
    app.run(debug=True)
