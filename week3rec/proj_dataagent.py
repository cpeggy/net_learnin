import os
import asyncio
import pandas as pd
from dotenv import load_dotenv
import chardet
import glob
import json
import re

# 載入 .env 檔案中的環境變數
load_dotenv()
print("Gemini_api:", os.environ.get("Gemini_api"))

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

async def read_md_files(file_paths):
    """
    讀取多個 .md 檔案，並將它們的內容返回為一個字符串清單。
    """
    md_content = []
    for file_path in file_paths:
        print(f"正在讀取 {file_path} ...")
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            md_content.append(content)
    print(f"總共讀取到 {len(md_content)} 個 MD 檔案")
    return md_content

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition, md_content):
    """
    處理單一批次資料，並結合讀取的 .md 文件內容提供給代理人。
    只存入最終 Persona，而非完整對話紀錄。
    """
    chunk_data = chunk.to_dict(orient='records')
    print(f"處理批次起始索引 {start_idx}, 批次筆數: {len(chunk)}")
    
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆問卷資料（共 {total_records} 筆）。\n"
        f"以下為該批次問卷資料:\n{chunk_data}\n\n"
        "這是訪談的資料：\n" + "\n".join(md_content) + "\n"
        "請根據以上問卷資料與訪談進行分析，**生成課程受眾的 persona 概觀**，"
        "此外，請 MultimodalWebSurfer 搜尋外部網站，尋找最新的泰文學習建議的學習資源，\n"
        "並將搜尋結果整合到 persona 概觀。\n"
        "請將輸出格式為 JSON，範例如下：\n"
        "```json\n"
        "{\n"
        '  "persona_id": "A",\n'
        '  "description": "這是一位對泰語有興趣的學習者...",\n'
        '  "motivation": "...",\n'
        '  "challenges": "...",\n'
        '  "learning_goals": "...",\n'
        '  "preferred_learning_methods": "...",\n'
        '  "suggested_learning_resources": [...]\n'
        "}\n"
        "```\n"
        "請確保輸出符合 JSON 格式，並且只包含 persona 概述，而不是對話過程。\n"
    )

    assistant_1 = AssistantAgent("data_agent", model_client)
    web_surfer = MultimodalWebSurfer("web_surfer", model_client)
    assistant_2 = AssistantAgent("assistant", model_client)
    report_generator = AssistantAgent("report_generator", model_client)

    local_team = RoundRobinGroupChat(
        [assistant_1, web_surfer, assistant_2, report_generator],
        termination_condition=termination_condition,
    )

    messages = []
    personas = []  # 存放解析出的 persona
    async for event in local_team.run_stream(task=prompt):
        if isinstance(event, TextMessage):
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

            # 只提取 JSON 格式的 persona 內容
            match = re.search(r"```json\n(.*?)\n```", event.content, re.DOTALL)
            if match:
                try:
                    persona_data = json.loads(match.group(1))
                    print("成功提取到 persona JSON:", persona_data)
                    personas.append(persona_data)
                except json.JSONDecodeError:
                    print("⚠ JSON 解析失敗，可能是格式錯誤")
    return messages, personas

async def main():
    gemini_api_key = os.environ.get("Gemini_api")
    if not gemini_api_key:
        print("請檢查 .env 檔案中的 GEMINI_API_KEY。")
        return

    model_client = OpenAIChatCompletionClient(
        model="gemini-2.0-flash",
        api_key=gemini_api_key,
    )

    termination_condition = TextMentionTermination("TERMINATE")

    md_file_paths = glob.glob("/Users/Peggy/Documents/113-2 net_learning/week3/*.md")
    print("開始讀取 MD 檔案...")
    md_content = await read_md_files(md_file_paths)

    csv_file_path = "/Users/Peggy/Documents/113-2 net_learning/week3/課程問券_泰文課.csv"
    chunk_size = 1000
    with open(csv_file_path, 'rb') as f:
        raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        print(f"檢測到的編碼格式: {encoding}")

    try:
        chunks = list(pd.read_csv(csv_file_path, chunksize=chunk_size, encoding=encoding))
        print(f"成功讀取 CSV 檔案: {csv_file_path}")
    except Exception as e:
        print(f"無法讀取 CSV 檔案: {e}")
        return

    total_records = sum(chunk.shape[0] for chunk in chunks)
    print(f"CSV 總筆數: {total_records}")

    print("開始處理各個批次資料...")
    tasks = [
        process_chunk(chunk, idx * chunk_size, total_records, model_client, termination_condition, md_content)
        for idx, chunk in enumerate(chunks)
    ]
    results = await asyncio.gather(*tasks)
    print("所有批次處理完成")

    # 分離出 persona 與對話紀錄
    all_messages = []
    all_personas = []
    for batch_messages, batch_personas in results:
        all_messages.extend(batch_messages)
        all_personas.extend(batch_personas)

    # 儲存對話紀錄
    df_log = pd.DataFrame(all_messages)
    output_file = "all_conve_log.csv"
    df_log.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"已將所有對話紀錄輸出為 {output_file}")

    # 儲存 persona 結果到 JSON
    output_persona_file = "persona.json"
    with open(output_persona_file, "w", encoding="utf-8") as f:
        json.dump({"personas": all_personas}, f, ensure_ascii=False, indent=4)
    print(f"已成功將 Personas 存入 {output_persona_file}")

if __name__ == '__main__':
    asyncio.run(main())