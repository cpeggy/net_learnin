import os
import asyncio
import pandas as pd
from dotenv import load_dotenv
import io
import chardet

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition):
    """
    處理單一批次資料：
      - 將該批次資料轉成 dict 格式
      - 組出提示，要求各代理人根據該批次問卷資料進行分析，
        並提供受訪者的 persona 概觀。
      - 請 MultimodalWebSurfer 代理人搜尋外部網站，尋找最新的日檢學習建議，
        並將結果整合到分析中。
      - 收集所有回覆訊息並返回。
    """
    # 將資料轉成 dict 格式
    chunk_data = chunk.to_dict(orient='records')
    
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆問卷資料（共 {total_records} 筆）。\n"
        f"以下為該批次問卷資料:\n{chunk_data}\n\n"
        "請根據以上問卷資料進行分析，並生成受訪者的 persona 概觀，特別包含以下要素：\n"
        "  1. 受訪者的動機：他們為何想要考取日檢 N4/N3；\n"
        "  2. 挑戰與困難點：受訪者在備考過程中遇到的最大挑戰；\n"
        "  3. 日文程度：受訪者目前的日文能力；\n"
        "  4. 目標：受訪者是否專注於 N4 或 N3，或兩者都要準備；\n"
        "  5. 最感興趣的學習方式：他們對不同學習方式（如單字卡、聽解訓練）的偏好。\n"
        "此外，請 MultimodalWebSurfer 搜尋外部網站，尋找最新的日檢學習建議（例如 N4/N3 的學習資源），"
        "並將搜尋結果整合到建議中。\n"
        "請各代理人協同合作，提供完整且具參考價值的 persona 概觀與學習建議。"
    )
    
    # 為每個批次建立新的 agent 與 team 實例
    local_data_agent = AssistantAgent("data_agent", model_client)
    local_web_surfer = MultimodalWebSurfer("web_surfer", model_client)
    local_assistant = AssistantAgent("assistant", model_client)
    local_user_proxy = UserProxyAgent("user_proxy")
    local_team = RoundRobinGroupChat(
        [local_data_agent, local_web_surfer, local_assistant, local_user_proxy],
        termination_condition=termination_condition
    )
    
    messages = []
    async for event in local_team.run_stream(task=prompt):
        if isinstance(event, TextMessage):
            # 印出目前哪個 agent 正在運作，方便追蹤
            print(f"[{event.source}] => {event.content}\n")
            messages.append({
                "batch_start": start_idx,
                "batch_end": start_idx + len(chunk) - 1,
                "source": event.source,
                "content": event.content,
                "type": event.type,
                "prompt_tokens": event.models_usage.prompt_tokens if event.models_usage else None,
                "completion_tokens": event.models_usage.completion_tokens if event.models_usage else None
            })
    return messages

async def main():
    gemini_api_key = os.environ.get("Gemini_api")
    if not gemini_api_key:
        print("請檢查 .env 檔案中的 GEMINI_API_KEY。")
        return

    # 初始化模型用戶端 (此處示範使用 gemini-2.0-flash)
    model_client = OpenAIChatCompletionClient(
        model="gemini-2.0-flash",
        api_key=gemini_api_key,
    )
    
    termination_condition = TextMentionTermination("TERMINATE")
    
    # 使用 pandas 以 chunksize 方式讀取 CSV 檔案
    csv_file_path = "/Users/Peggy/Documents/113-2 net_learning/week3/課程問券日檢_test.csv"
    chunk_size = 1000
    # 檢測檔案編碼
    with open(csv_file_path, 'rb') as f:
        raw_data = f.read(10000)  # 讀取檔案的前 10,000 個字節進行檢測
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        print(f"檢測到的編碼格式: {encoding}")

    # 使用檢測到的編碼格式來讀取檔案
    try:
        chunks = list(pd.read_csv(csv_file_path, chunksize=chunk_size, encoding=encoding))
        print(f"成功讀取檔案: {csv_file_path}")
    except Exception as e:
        print(f"無法讀取檔案: {e}")
        
        try:
            chunks = list(pd.read_csv(csv_file_path, chunksize=chunk_size))
            print(f"成功讀取檔案，總共讀取 {len(chunks)} 個批次資料")
        except Exception as e:
            print(f"無法讀取檔案: {e}")
            return
    
    total_records = sum(chunk.shape[0] for chunk in chunks)
    
    # 利用 map 與 asyncio.gather 同時處理所有批次（避免使用傳統 for 迴圈）
    tasks = list(map(
        lambda idx_chunk: process_chunk(
            idx_chunk[1],
            idx_chunk[0] * chunk_size,
            total_records,
            model_client,
            termination_condition
        ),
        enumerate(chunks)
    ))
    
    results = await asyncio.gather(*tasks)
    # 將所有批次的訊息平坦化成一個清單
    all_messages = [msg for batch in results for msg in batch]
    
    # 將對話紀錄整理成 DataFrame 並存成 CSV
    df_log = pd.DataFrame(all_messages)
    output_file = "all_conve_log.csv"
    df_log.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"已將所有對話紀錄輸出為 {output_file}")

if __name__ == '__main__':
    asyncio.run(main())