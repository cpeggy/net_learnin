import os
import json
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

# 載入 .env 中的環境變數
load_dotenv()

# 從 .env 檔案中獲取 API 金鑰和搜尋引擎 ID
google_api_key = os.getenv("GOOGLE_API_KEY")
google_cx = os.getenv("GOOGLE_CX")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# 搜索範圍（例如泰語學習）
QUERY = "泰語學習問題"

# 定義分類項目
CATEGORIES = [
    "語法問題",
    "發音問題",
    "聽力問題",
    "詞彙問題",
    "文化理解問題",
    "口說練習",
    "語言學習技巧"
]

# 使用 Google Custom Search API 進行搜尋
def fetch_search_results(query, api_key, cx, num_results=10):
    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": api_key,
        "cx": cx,
        "num": num_results
    }
    response = requests.get(search_url, params=params)
    if response.status_code == 200:
        results = response.json()
        return results["items"]
    else:
        print(f"Error: {response.status_code}")
        return []

# 從搜尋結果中提取標題、描述和鏈接
def parse_search_results(results):
    search_data = []
    for result in results:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        link = result.get("link", "")
        search_data.append({"title": title, "snippet": snippet, "link": link})
    return search_data

# 嘗試解析 Gemini API 回傳的 JSON 格式結果
def parse_response(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    
    try:
        result = json.loads(cleaned)
        for item in CATEGORIES:
            if item not in result:
                result[item] = ""
        return result
    except Exception as e:
        print(f"解析 JSON 失敗：{e}")
        return {item: "" for item in CATEGORIES}

# 使用 Gemini API 分類批次處理的討論
def process_batch_dialogue(client, dialogues: list, delimiter="-----"):
    prompt = (
        "你是一位語言學習問題分類專家，請根據以下分類項目對每條學生討論進行分類：\n"
        + "\n".join(CATEGORIES) +
        "\n\n請根據討論內容將每個問題分類為相應的項目，並標記每個項目：若該項目涉及則標記為 1，否則留空。"
        " 請對每條討論產生 JSON 格式回覆，並在各條結果間用下列分隔線隔開：\n"
        f"{delimiter}\n"
        "例如：\n"
        "```json\n"
        "{\n  \"語法問題\": \"1\",\n  \"發音問題\": \"\",\n  ...\n}\n"
        f"{delimiter}\n"
        "{{...}}\n```"
    )
    batch_text = f"\n{delimiter}\n".join(dialogues)
    content = prompt + "\n\n" + batch_text

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content
        )
    except ServerError as e:
        print(f"API 呼叫失敗：{e}")
        return [{item: "" for item in CATEGORIES} for _ in dialogues]
    
    print("批次 API 回傳內容：", response.text)
    parts = response.text.split(delimiter)
    results = []
    for part in parts:
        part = part.strip()
        if part:
            results.append(parse_response(part))
    return results

# 計算分類項目的統計數據
def calculate_category_counts(results):
    counts = {category: 0 for category in CATEGORIES}
    for result in results:
        for category in CATEGORIES:
            if result.get(category) == "1":
                counts[category] += 1
    return counts

# 主程式
def main():
    # 使用搜尋代理來抓取與泰語學習相關的討論
    search_results = fetch_search_results(QUERY, google_api_key, google_cx, num_results=10)
    search_data = parse_search_results(search_results)

    # 將搜尋結果轉換為討論內容
    dialogues = [item["snippet"] for item in search_data]
    
    # 載入 GEMINI API 客戶端
    if not gemini_api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")
    client = genai.Client(api_key=gemini_api_key)

    # 處理批次並儲存結果
    batch_results = process_batch_dialogue(client, dialogues)

    # 計算分類項目的統計數據
    category_counts = calculate_category_counts(batch_results)

    # 合併搜尋結果和分類結果
    for i, result in enumerate(batch_results):
        result.update(search_data[i])  # 將標題、描述和鏈接加到分類結果中

    # 將結果儲存到 CSV
    results_df = pd.DataFrame(batch_results)
    results_df.to_csv("classified_search_results_with_details.csv", index=False, encoding="utf-8-sig")

    # 儲存分類統計結果
    stats_df = pd.DataFrame([category_counts])
    stats_df.to_csv("category_summary.csv", index=False, encoding="utf-8-sig")

    print("結果已儲存至 classified_search_results_with_details.csv 和 category_summary.csv")

if __name__ == "__main__":
    main()
