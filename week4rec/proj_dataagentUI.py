import os
import asyncio
import pandas as pd
from dotenv import load_dotenv
import chardet
import glob
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

async def process_chunk(chunk, start_idx, total_records, model_client, termination_condition, md_content):
    """處理單一批次資料，從 agent 回應中只擷取最終 persona JSON"""
    chunk_data = chunk.to_dict(orient='records')
    print(f"處理批次起始索引 {start_idx}, 批次筆數: {len(chunk)}")
    
    prompt = (
        f"目前正在處理第 {start_idx} 至 {start_idx + len(chunk) - 1} 筆問卷資料（共 {total_records} 筆）。\n"
        f"以下為該批次問卷資料:\n{chunk_data}\n\n"
        "這是訪談的資料：\n" + "\n".join(md_content) + "\n"
        "請根據以上問卷資料與訪談進行分析，**生成課程受眾的 persona 概觀**，"
        "此外，請 MultimodalWebSurfer 搜尋外部網站，尋找最新的泰文學習建議的學習資源，\n"
        "並將搜尋結果整合到 persona 概觀中。\n"
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
    last_persona = None

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

            match = re.search(r"```json\n(.*?)\n```", event.content, re.DOTALL)
            if match:
                try:
                    persona_data = json.loads(match.group(1))
                    print("成功提取到 persona JSON:", persona_data)
                    last_persona = persona_data
                except json.JSONDecodeError:
                    print("⚠ JSON 解析失敗，可能是格式錯誤")
    if last_persona:
        personas.append(last_persona)
    print("本批次資料處理完成。")
    return messages, personas

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
    for idx, chunk in enumerate(chunks):
        print(f"排程處理第 {idx} 批次資料")
        tasks.append(process_chunk(chunk, idx * 1000, total_records, model_client, termination_condition, md_content))
    results = await asyncio.gather(*tasks)
    print("所有批次處理完成。")

    all_messages = []
    all_personas = []
    for batch_messages, batch_personas in results:
        all_messages.extend(batch_messages)
        all_personas.extend(batch_personas)

    output_csv = "all_conve_log.csv"
    output_persona = "persona.json"
    df_log = pd.DataFrame(all_messages)
    df_log.to_csv(output_csv, index=False, encoding="utf-8-sig")
    with open(output_persona, "w", encoding="utf-8") as f:
        json.dump({"personas": all_personas}, f, ensure_ascii=False, indent=4)
    print("輸出檔案已生成。")
    return output_csv, output_persona

# Gradio 前端函數
def process_files(csv_file, md_files):
    """
    csv_file: 上傳的 CSV 檔案（可能為檔案路徑字串或 file-like 物件）
    md_files: 上傳的 MD 檔案列表（每個皆可能為檔案路徑字串或 file-like 物件）
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        # 處理 CSV 檔案：將上傳的檔案內容寫入暫存檔
        csv_path = os.path.join(tmpdirname, "input.csv")
        if isinstance(csv_file, str):
            shutil.copy(csv_file, csv_path)
        elif hasattr(csv_file, "read"):
            with open(csv_path, "wb") as f:
                f.write(csv_file.read())
        else:
            with open(csv_path, "wb") as f:
                f.write(csv_file)
                
        # 處理 MD 檔案
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
            
        # 進入暫存目錄進行後續處理
        current_dir = os.getcwd()
        os.chdir(tmpdirname)
        try:
            output_csv, output_persona = asyncio.run(process_all(csv_path, md_paths))
            # 將產生的檔案複製到當前工作目錄（持久性路徑），這樣 Gradio 能取得檔案路徑
            dest_csv = os.path.join(current_dir, "all_conve_log.csv")
            dest_json = os.path.join(current_dir, "persona.json")
            shutil.copy(output_csv, dest_csv)
            shutil.copy(output_persona, dest_json)
        finally:
            os.chdir(current_dir)
        # 回傳檔案路徑（字串），Gradio File 組件會以此作為下載檔案
        return dest_csv, dest_json

# 建立 Gradio 介面，並加入「開始」按鈕
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
    demo.launch()