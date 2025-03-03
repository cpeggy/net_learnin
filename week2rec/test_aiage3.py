import os
from dotenv import load_dotenv
import asyncio

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

async def main():
    # 從 .env 讀取 Gemini API 金鑰
    gemini_api_key = os.environ.get("Gemini_api")
    
    # 使用 Gemini API，指定 model 為 "gemini-1.5-flash-8b"
    model_client = OpenAIChatCompletionClient(
        model="gemini-1.5-flash-8b",
        api_key=gemini_api_key,
    )
    
    # 建立各代理人
    assistant = AssistantAgent("assistant", model_client)
    web_surfer = MultimodalWebSurfer("web_surfer", model_client)
    critic = AssistantAgent("critic", model_client)
    
    # 當對話中出現 "exit" 時即終止對話
    termination_condition = TextMentionTermination("TERMINATE")
    
    # 建立一個循環團隊，讓各代理人依序參與討論
    team = RoundRobinGroupChat(
        [web_surfer, assistant, critic],
        termination_condition=termination_condition
    )
    
    # 先執行一次對話，確保至少運行一次
    await Console(team.run_stream(task="請搜尋 AI 的相關資訊，並撰寫一份簡短摘要。"))

    # 檢查是否符合終止條件，若未達成則繼續執行
    should_continue = True
    while should_continue:
        # 再次執行對話
        await Console(team.run_stream(task="請搜尋更多 AI 相關資訊。"))
        # 假設 `termination_condition.check_condition()` 是檢查是否應該結束對話的函數
        should_continue = not termination_condition.check_condition()
    
if __name__ == '__main__':
    asyncio.run(main())