import os
import asyncio
import pandas as pd
import json
from dotenv import load_dotenv
import chardet
import tempfile
import shutil
import gradio as gr
import re
import zipfile

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 檢查是否為有效資料（忽略空白或占位符的欄位）
def is_valid_persona(persona):
    """檢查 persona 是否有效"""
    if persona["description"] == "..." or persona["motivation"] == "..." or persona["challenges"] == "..." or persona["learning_goals"] == "..." or persona["preferred_learning_methods"] == "...":
        return False
    if any(res["feature_name"] == "..." or res["description"] == "..." or res["justification"] == "..." for res in persona["suggested_learning_resources"]):
        return False
    return True

# 處理單一批次資料
async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition):
    chunk_data = chunk.to_dict(orient='records')
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆問卷資料（共 {total_records} 筆）。\n"
        "請根據以上問卷資料行分析，生成完整的課程受眾的 persona 概觀，"
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
            messages.append({
                "batch_start": start_idx,
                "batch_end": start_idx + len(chunk) - 1,
                "source": event.source,
                "content": event.content,
                "type": event.type,
            })
            matches = re.findall(r"```json\n(.*?)\n```", event.content, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, list):
                        for persona in parsed:
                            if is_valid_persona(persona):
                                personas.append(persona)
                    elif isinstance(parsed, dict):
                        if is_valid_persona(parsed):
                            personas.append(parsed)
                except json.JSONDecodeError as e:
                    print(f"JSON解析失敗: {e}")
    return messages, personas

async def process_all(csv_path):
    with open(csv_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    print(f"檢測到的 CSV 編碼格式: {encoding}")

    try:
        chunks = list(pd.read_csv(csv_path, chunksize=1000, encoding=encoding))
    except Exception as e:
        print(f"無法讀取 CSV 檔案: {e}")
        return None, None

    total_records = sum(chunk.shape[0] for chunk in chunks)
    gemini_api_key = os.environ.get("Gemini_api")
    model_client = OpenAIChatCompletionClient(model="gemini-2.0-flash", api_key=gemini_api_key)
    termination_condition = TextMentionTermination("TERMINATE")

    tasks = []

    # 處理批次資料
    for idx, chunk in enumerate(chunks):
        tasks.append(process_chunk(chunk, idx * 1000, total_records, model_client, termination_condition))

    results = await asyncio.gather(*tasks)
    all_messages = []
    all_personas = []
    for batch_messages, batch_personas in results:
        all_messages.extend(batch_messages)
        all_personas.extend(batch_personas)

    output_csv = "all_conve_log.csv"
    df_log = pd.DataFrame(all_messages)
    df_log.to_csv(output_csv, index=False, encoding="utf-8-sig")

    # 創建 ZIP 檔案
    zip_filename = "personas.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for persona in all_personas:
            if persona.get("persona_id"):
                persona_id = persona["persona_id"]
                file_name = f"PERSONA-{persona_id}.json"
                with open(file_name, 'w', encoding='utf-8') as json_file:
                    json.dump(persona, json_file, ensure_ascii=False, indent=4)
                zipf.write(file_name)
                os.remove(file_name)  # 刪除暫時檔案

    return output_csv, zip_filename

def process_files(csv_file):
    with tempfile.TemporaryDirectory() as tmpdirname:
        csv_path = os.path.join(tmpdirname, "input.csv")
        shutil.copy(csv_file, csv_path)

        current_dir = os.getcwd()
        os.chdir(tmpdirname)
        try:
            output_csv, output_zip = asyncio.run(process_all(csv_path))
            dest_csv = os.path.join(current_dir, output_csv)
            dest_zip = os.path.join(current_dir, output_zip)
            shutil.copy(output_csv, dest_csv)
            shutil.copy(output_zip, dest_zip)
        finally:
            os.chdir(current_dir)
        return dest_csv, dest_zip


with gr.Blocks() as demo:
    gr.Markdown("# Persona 分析系統")
    with gr.Row():
        csv_input = gr.File(label="上傳 CSV 檔案", file_count="single")
    start_btn = gr.Button("開始")
    with gr.Row():
        csv_output = gr.File(label="下載對話紀錄 CSV")
        zip_output = gr.File(label="下載 Persona JSON (ZIP)")
    start_btn.click(fn=process_files, inputs=[csv_input], outputs=[csv_output, zip_output])

if __name__ == '__main__':
    demo.launch(share=True)