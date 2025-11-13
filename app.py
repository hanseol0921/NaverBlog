from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

# 네이버 API 인증 정보
CLIENT_ID = "m6nZpyW187lm1c7iMKSH"
CLIENT_SECRET = "OBrpyxklnJ"

NAVER_API_URL = "https://openapi.naver.com/v1/search/blog.json"

@app.route('/blog', methods=['GET', 'POST'])
def search_blog():
    search_results = None
    if request.method == 'POST':
        query = request.form.get('query')
        if query:

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


# 메인 페이지
@app.route('/')
def home():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
