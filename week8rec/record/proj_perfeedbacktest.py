import json
import os
import gradio as gr
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv
import asyncio

# 載入環境變數
load_dotenv()

# 載入 persona
def load_persona(persona_file):
    """載入 persona 資料"""
    with open(persona_file, 'r', encoding='utf-8') as file:
        persona = json.load(file)
    return persona

# 評估行銷文案並提供回饋
async def evaluate_with_autoagent(persona, marketing_copy):
    """根據 persona 評估行銷文案並提供回饋"""
    
    # 設定提示詞（繁體中文）
    prompt = f"""
    你正在扮演一個 persona，這個 persona 的描述如下：
    {persona['description']}

    以下是課程的行銷文案：
    "{marketing_copy}"

    請根據你的 persona 回答以下問題：
    1. 你對這篇文案的購買意願是多少？（1-10分，數字越大代表越有意願購買）
    2. 你想購買的原因是什麼？
    3. 你為什麼沒有被打動購買這個課程？
    """
    
    # 創建模型客戶端及代理
    gemini_api_key = os.getenv("Gemini_api")
    model_client = OpenAIChatCompletionClient(model="gemini-2.0-flash", api_key=gemini_api_key)
    termination_condition = TextMentionTermination("TERMINATE")

    assistant = AssistantAgent("persona_assistant", model_client)
    group_chat = RoundRobinGroupChat([assistant], termination_condition=termination_condition)

    # 執行代理並取得回應
    messages = []
    async for event in group_chat.run_stream(task=prompt):
        if isinstance(event, TextMessage):
            messages.append({
                "content": event.content,
                "source": event.source
            })

    return messages

# 處理評估過程
def process_evaluation(persona_file, marketing_copy):
    """載入 persona 並評估行銷文案"""
    persona = load_persona(persona_file)
    response = asyncio.run(evaluate_with_autoagent(persona, marketing_copy))
    feedback = ""
    for msg in response:
        feedback += f"來源: {msg['source']}\n回饋: {msg['content']}\n\n"
    return feedback

# 前端界面設定（Gradio）
def gradio_interface(persona_file, marketing_copy):
    """Gradio 界面函數"""
    feedback = process_evaluation(persona_file.name, marketing_copy)
    return feedback

# 設置 Gradio 界面
with gr.Blocks() as demo:
    gr.Markdown("# Persona 行銷文案評估系統")
    
    # 上傳檔案區
    with gr.Row():
        persona_file = gr.File(label="上傳 Persona JSON 檔案", file_count="single")
        marketing_copy = gr.Textbox(label="輸入行銷文案", placeholder="請輸入或粘貼行銷文案", lines=10)
    
    start_btn = gr.Button("開始評估")
    
    # 回饋顯示區
    output_feedback = gr.Textbox(label="回饋結果", lines=10, interactive=False)

    start_btn.click(fn=gradio_interface, inputs=[persona_file, marketing_copy], outputs=[output_feedback])

if __name__ == '__main__':
    demo.launch(share=True)
