import os
import asyncio
import pandas as pd
from dotenv import load_dotenv
import chardet
import json
import re
import tempfile
import shutil
import zipfile
import gradio as gr

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

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

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition, md_content):
    """處理單一批次資料"""
    chunk_data = chunk
    print(f"處理批次起始索引 {start_idx}, 批次筆數: {len(chunk)}")

    prompt = (
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

    assistant_1 = AssistantAgent("data_agent", model_client)
    assistant_2 = AssistantAgent("assistant", model_client)
    report_generator = AssistantAgent("report_generator", model_client)

    local_team = RoundRobinGroupChat(
        [assistant_1, assistant_2, report_generator],
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
                            with open("persona_output.json", "a", encoding="utf-8") as f:
                                json.dump(persona, f, ensure_ascii=False, indent=4)
                    elif isinstance(parsed, dict):
                        personas.append(parsed)
                        with open("persona_output.json", "a", encoding="utf-8") as f:
                            json.dump(parsed, f, ensure_ascii=False, indent=4)
                except json.JSONDecodeError as e:
                    print(f"JSON解析失敗: {e}")
    return messages, personas

async def process_all(md_paths):
    md_content = await read_md_files_from_paths(md_paths)

    gemini_api_key = os.environ.get("Gemini_api")
    model_client = OpenAIChatCompletionClient(model="gemini-2.0-flash", api_key=gemini_api_key)
    termination_condition = TextMentionTermination("TERMINATE")

    tasks = []
    
    # 處理批次資料
    for idx, content in enumerate(md_content):
        tasks.append(process_chunk(content, idx * 1000, len(md_content), model_client, termination_condition, md_content))

    results = await asyncio.gather(*tasks)
    all_messages = []
    all_personas = []
    for batch_messages, batch_personas in results:
        all_messages.extend(batch_messages)
        all_personas.extend(batch_personas)

    # 輸出 CSV 內容
    output_csv = "all_conve_log.csv"
    df_log = pd.DataFrame(all_messages)
    df_log.to_csv(output_csv, index=False, encoding="utf-8-sig")

    # 儲存分析結果為 JSON 檔案
    output_json = "all_personas.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_personas, f, ensure_ascii=False, indent=4)

    return output_csv, output_json

def process_files(md_files):
    with tempfile.TemporaryDirectory() as tmpdirname:
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
            output_csv, output_json = asyncio.run(process_all(md_paths))
            dest_csv = os.path.join(current_dir, output_csv)
            dest_json = os.path.join(current_dir, output_json)
            shutil.copy(output_csv, dest_csv)
            shutil.copy(output_json, dest_json)
        finally:
            os.chdir(current_dir)
        return dest_csv, dest_json

def save_personas_to_zip(personas, output_zip):
    """將每個有效的 persona 儲存為單獨的 JSON 檔案，並壓縮成 zip 檔案"""
    output_dir = "/tmp/personas"
    os.makedirs(output_dir, exist_ok=True)

    # 儲存每個 persona 為 JSON 檔案
    for persona in personas:
        if persona.get("description") != "..." and persona.get("motivation") != "...":
            persona_id = persona.get("persona_id")
            file_name = f"PERSONA-{persona_id}.json"
            file_path = os.path.join(output_dir, file_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(persona, f, ensure_ascii=False, indent=4)

    # 壓縮所有檔案為 zip
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                zipf.write(os.path.join(root, file), file)

    print(f"所有 persona 檔案已壓縮為 {output_zip}")
    return output_zip

# Gradio 用戶介面處理
def process_files_and_zip(md_files):
    with tempfile.TemporaryDirectory() as tmpdirname:
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
            output_csv, output_json = asyncio.run(process_all(md_paths))

            # 儲存 persona JSON 並壓縮為 zip 檔案
            output_zip = "/tmp/personas.zip"
            with open(output_json, 'r', encoding='utf-8') as f:
                all_personas = json.load(f)
            zip_file = save_personas_to_zip(all_personas, output_zip)

            # 將生成的 CSV 和壓縮檔案移到原始目錄
            dest_csv = os.path.join(current_dir, output_csv)
            dest_json = os.path.join(current_dir, output_json)
            shutil.copy(output_csv, dest_csv)
            shutil.copy(zip_file, os.path.join(current_dir, "personas.zip"))
            
        finally:
            os.chdir(current_dir)
        return dest_csv, "personas.zip"

# Gradio 介面
with gr.Blocks() as demo:
    gr.Markdown("# Persona 分析系統")
    with gr.Row():
        md_input = gr.File(label="上傳 MD 檔案", file_count="multiple")
    start_btn = gr.Button("開始")
    with gr.Row():
        csv_output = gr.File(label="下載對話紀錄 CSV")
        zip_output = gr.File(label="下載 persona Zip")
    start_btn.click(fn=process_files_and_zip, inputs=[md_input], outputs=[csv_output, zip_output])

if __name__ == '__main__':
    demo.launch(share=True)