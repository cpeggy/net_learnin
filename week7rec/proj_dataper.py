import os
import asyncio
import pandas as pd
from dotenv import load_dotenv
import chardet
import json
import re
import tempfile
import shutil
import gradio as gr

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

async def read_md_files_from_paths(file_paths):
    """讀取多個 .md 檔案，返回內容列表"""
    md_content = []
    for file_path in file_paths:
        print(f"正在讀取 {file_path} ...")
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            md_content.append(content)
    print(f"總共讀取到 {len(md_content)} 個 MD 檔案")
    return md_content

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition, md_content, persona_file):
    """處理單一批次資料，從 agent 回應中提取所有與 persona 相關的敘述並寫入檔案"""
    chunk_data = chunk.to_dict(orient='records')
    print(f"處理批次起始索引 {start_idx}, 批次筆數: {len(chunk)}")
    
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆問卷資料（共 {total_records} 筆）。\n"
        f"以下為該批次問卷資料:\n{chunk_data}\n\n"
        "這是訪談的資料：\n" + "\n".join(md_content) + "\n\n"
        "請根據以上問卷資料與訪談進行分析，生成完整的課程受眾的 persona 概觀，"
        "須包含下列欄位：\n"
        "- persona_id (以數字為主，從1開始列到n)\n"
        "- description (對該 persona 的整體描述)\n"
        "- motivation (該 persona 學習動機)\n"
        "- challenges (該 persona 面臨挑戰與痛點)\n"
        "- learning_goals (該 persona 學習目標)\n"
        "- preferred_learning_methods (該 persona 偏好的學習方式)\n"
        "- suggested_learning_resources (該 persona 推薦的學習資源，每個資源包含 feature_name, description, justification)\n\n"
        "請以 JSON 格式輸出，格式範例如下：\n"
        "```json\n"
        "{\n"
        '  "persona_id": "1",\n'
        '  "description": "...",\n'
        '  "motivation": "...",\n'
        '  "challenges": "...",\n'
        '  "learning_goals": "...",\n'
        '  "preferred_learning_methods": "...",\n'
        '  "suggested_learning_resources": [\n'
        "      {\n"
        '         "feature_name": "...",\n'
        '         "description": "...",\n'
        '         "justification": "..." \n'
        "      }\n"
        "  ]\n"
        "}\n"
        "```\n"
        "請確保只輸出上述 JSON，不要包含其他對話內容。\n"
    )

    # 建立各個 agent
    assistant_1 = AssistantAgent("data_agent", model_client)
    web_surfer = MultimodalWebSurfer("web_surfer", model_client)
    assistant_2 = AssistantAgent("assistant", model_client)
    report_generator = AssistantAgent("report_generator", model_client)

    local_team = RoundRobinGroupChat(
        [assistant_1, web_surfer, assistant_2, report_generator],
        termination_condition=termination_condition,
    )

    messages = []
    personas = []

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
            # 使用正則表達式匹配所有以 ```json 開頭的區塊
            matches = re.findall(r"```json\n(.*?)\n```", event.content, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, list):
                        for persona in parsed:
                            personas.append(persona)
                            with open(persona_file, "a", encoding="utf-8") as f:
                                f.write(f"persona_id: {persona.get('persona_id','')}\n")
                                f.write(f"description: {persona.get('description','')}\n")
                                f.write(f"motivation: {persona.get('motivation','')}\n")
                                f.write(f"challenges: {persona.get('challenges','')}\n")
                                f.write(f"learning_goals: {persona.get('learning_goals','')}\n")
                                f.write(f"preferred_learning_methods: {persona.get('preferred_learning_methods','')}\n")
                                f.write(f"suggested_learning_resources: {persona.get('suggested_learning_resources','')}\n")
                                f.write("\n" + "-"*50 + "\n")
                    elif isinstance(parsed, dict):
                        personas.append(parsed)
                        with open(persona_file, "a", encoding="utf-8") as f:
                            f.write(f"persona_id: {parsed.get('persona_id','')}\n")
                            f.write(f"description: {parsed.get('description','')}\n")
                            f.write(f"motivation: {parsed.get('motivation','')}\n")
                            f.write(f"challenges: {parsed.get('challenges','')}\n")
                            f.write(f"learning_goals: {parsed.get('learning_goals','')}\n")
                            f.write(f"preferred_learning_methods: {parsed.get('preferred_learning_methods','')}\n")
                            f.write(f"suggested_learning_resources: {parsed.get('suggested_learning_resources','')}\n")
                            f.write("\n" + "-"*50 + "\n")
                    else:
                        print("提取到的資料既不是字典也不是列表")
                except json.JSONDecodeError as e:
                    print(f"JSON解析失敗: {e}")
    print("本批次資料處理完成。")
    return messages, personas

import json
import datetime

# 假設 all_personas 已經是你讀取過的資料

def check_and_fix_json(all_personas):
    invalid_items = []
    for idx, item in enumerate(all_personas):
        try:
            # 嘗試將每個項目轉換成 JSON 格式
            json.dumps(item, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # 如果發生錯誤，記錄該項目
            invalid_items.append({"index": idx, "error": str(e), "item": item})
    
    if invalid_items:
        # 輸出無效的項目
        print("以下項目無法轉換成有效的 JSON 格式:")
        for item in invalid_items:
            print(f"Index: {item['index']} - Error: {item['error']}")
            print(f"Item: {item['item']}")
            # 嘗試修正資料
            all_personas[item['index']] = fix_item(item['item'])
    else:
        print("所有項目均可轉換為有效的 JSON 格式。")

def fix_item(item):
    """修正無效的資料項目"""
    # 假設出錯的是某些不可序列化的數據類型（如 datetime 或 None）
    for key, value in item.items():
        if isinstance(value, datetime.datetime):
            # 轉換 datetime 為字串
            item[key] = value.isoformat()
        elif value is None:
            # 轉換 None 為 null
            item[key] = "null"  # 或者使用空字串 ""
        elif isinstance(value, str) and not value.strip():
            # 去除空白的字串
            item[key] = "未知"  # 或者其他你想給的預設值
    return item

async def process_all(csv_path, md_paths):
    """根據上傳的 CSV 與 MD 檔案路徑，完成整個資料處理流程"""
    md_content = await read_md_files_from_paths(md_paths)
    
    with open(csv_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    print(f"檢測到的 CSV 編碼格式: {encoding}")

    try:
        chunks = list(pd.read_csv(csv_path, chunksize=1000, encoding=encoding))
        print(f"成功讀取 CSV 檔案: {csv_path}")
    except Exception as e:
        print(f"無法讀取 CSV 檔案: {e}")
        return None, None

    total_records = sum(chunk.shape[0] for chunk in chunks)
    print(f"CSV 總筆數: {total_records}")

    gemini_api_key = os.environ.get("Gemini_api")
    model_client = OpenAIChatCompletionClient(model="gemini-2.0-flash", api_key=gemini_api_key)
    termination_condition = TextMentionTermination("TERMINATE")

    tasks = []
    persona_file = "persona.txt"  # 指定 persona.txt 為存儲檔案

    # 清空檔案，準備寫入
    with open(persona_file, "w", encoding="utf-8") as f:
        f.write('')

    for idx, chunk in enumerate(chunks):
        print(f"排程處理第 {idx} 批次資料")
        tasks.append(process_chunk(chunk, idx * 1000, total_records, model_client, termination_condition, md_content, persona_file))
    results = await asyncio.gather(*tasks)
    print("所有批次處理完成。")

    all_messages = []
    all_personas = []
    for batch_messages, batch_personas in results:
        all_messages.extend(batch_messages)
        all_personas.extend(batch_personas)

    print("原始的 persona 資料：")
    print(all_personas)
    
    # 先檢查資料，並修正錯誤
    check_and_fix_json(all_personas)

    # 保存修正後的 JSON 格式
    with open("all_personas.json", "w", encoding="utf-8") as json_file:
        json.dump(all_personas, json_file, ensure_ascii=False, indent=4)

    output_csv = "all_conve_log.csv"
    df_log = pd.DataFrame(all_messages)
    df_log.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print("輸出檔案已生成 output_csv, all_personas.json")
    return output_csv, "all_personas.json"

def process_files(csv_file, md_files):
    """
    csv_file: 上傳的 CSV 檔案（可能為 file-like 物件或字串）
    md_files: 上傳的 MD 檔案列表（每個皆可能為 file-like 物件或字串）
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        csv_path = os.path.join(tmpdirname, "input.csv")
        if isinstance(csv_file, str):
            shutil.copy(csv_file, csv_path)
        elif hasattr(csv_file, "read"):
            with open(csv_path, "wb") as f:
                f.write(csv_file.read())
        else:
            with open(csv_path, "wb") as f:
                f.write(csv_file)
                
        md_paths = []
        for i, file in enumerate(md_files):
            md_path = os.path.join(tmpdirname, f"input_{i}.md")
            if isinstance(file, str):
                shutil.copy(file, md_path)
            elif hasattr(file, "read"):
                with open(md_path, "wb") as f:
                    f.write(file.read())
            else:
                with open(md_path, "wb") as f:
                    f.write(file)
            md_paths.append(md_path)
            
        current_dir = os.getcwd()
        os.chdir(tmpdirname)
        try:
            output_csv, output_json = asyncio.run(process_all(csv_path, md_paths))
            dest_csv = os.path.join(current_dir, "all_conve_log.csv")
            dest_json = os.path.join(current_dir, output_json)
            shutil.copy(output_csv, dest_csv)
            shutil.copy(output_json, dest_json)
        finally:
            os.chdir(current_dir)
        return dest_csv, dest_json


with gr.Blocks() as demo:
    gr.Markdown("# Persona 分析系統")
    with gr.Row():
        csv_input = gr.File(label="上傳 CSV 檔案", file_count="single")
        md_input = gr.File(label="上傳 MD 檔案", file_count="multiple")
    start_btn = gr.Button("開始")
    with gr.Row():
        csv_output = gr.File(label="下載對話紀錄 CSV")
        json_output = gr.File(label="下載 persona JSON")
    start_btn.click(fn=process_files, inputs=[csv_input, md_input], outputs=[csv_output, json_output])

if __name__ == '__main__':
    demo.launch(share=True)