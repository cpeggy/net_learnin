import os
from dotenv import load_dotenv
import asyncio
import warnings
warnings.filterwarnings("ignore", message="Finish reason mismatch")

# 載入 .env 檔案中的環境變數
load_dotenv()

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_core import CancellationToken  # ✅ 引入 CancellationToken

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
    
    # 當對話中出現 "exit" 時即終止對話
    termination_condition = TextMentionTermination("exit")
    
    # 建立一個循環團隊，讓各代理人依序參與討論
    team = RoundRobinGroupChat(
        [web_surfer, assistant],
        termination_condition=termination_condition
    )
    
    # ✅ 建立 cancellation token
    cancellation_token = CancellationToken()

    # ✅ 使用 asyncio.create_task 來運行團隊對話
    run_task = asyncio.create_task(
        team.run(
            task="請搜尋 Gemini 的相關資訊，並撰寫一份簡短摘要。",
            cancellation_token=cancellation_token,
        )
    )

    # ✅ 監控團隊運行，偵測是否需要取消
    try:
        while not run_task.done():
            await asyncio.sleep(1)  # 模擬監控間隔

        # 取得結果
        result = await run_task
        print("✅ 團隊任務完成:", result)

    except asyncio.CancelledError:
        print("❌ 任務已被取消。")
    except Exception as e:
        print(f"🚨 執行錯誤: {e}")


if __name__ == '__main__':
    asyncio.run(main())