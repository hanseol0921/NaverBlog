import sqlite3
from flask import Flask, render_template, request
import requests
import json

app = Flask(__name__)

# 네이버 API 인증 정보
CLIENT_ID = "m6nZpyW187lm1c7iMKSH"
CLIENT_SECRET = ""

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"
DB_PATH = "naverblog.db"


def init_db():
    """처음 실행할 때 검색어 테이블 없으면 만들어 줌"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_keyword (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            count INTEGER DEFAULT 1,
            last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
