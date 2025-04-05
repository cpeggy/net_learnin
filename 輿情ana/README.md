歡迎來玩玩看-->[gogogo](https://cpeggy-poa.onrender.com/)
不過在開始之前先看這份文件


# 使用程式前置作業：申請 Gemini API 和 Google Custom Search API

## 1. 申請 Gemini API

Gemini 是 Google 提供的對話式 AI 模型，您可以使用它來進行語言理解、對話生成等任務。以下是如何申請 Gemini API 的步驟：

### 步驟 1：前往 Google Cloud 平台
- 進入 [Google Cloud](https://cloud.google.com/).

### 步驟 2：註冊/登入 Google Cloud 帳戶
- 如果您尚未有 Google Cloud 帳戶，請先註冊 [Google Cloud 帳戶](https://cloud.google.com/free).

### 步驟 3：啟用 Gemini API
- 在 Google Cloud Console 頁面上，搜尋並選擇 "Gemini API"。
- 點擊 "啟用" 以啟用 API。

### 步驟 4：創建項目（Project）
- 在 Google Cloud Console 中創建一個新的專案。
- 輸入專案名稱並點擊 "創建"。

### 步驟 5：申請 API 金鑰
- 在 Google Cloud Console 中，前往 “API 和服務” > “憑證” > “創建憑證” > “API 金鑰”。
- 複製您的 API 金鑰並保存在安全的地方。

### 步驟 6：使用 API
- 使用您的 API 金鑰開始訪問 Gemini API。詳細文檔可以參考 [Gemini API Documentation](https://cloud.google.com/genai/docs).

---

## 2. 申請 Google Custom Search API

Google Custom Search 是 Google 提供的搜尋引擎，允許開發者創建定制化的搜尋引擎以搜尋特定的網站或網頁。以下是如何申請 Google Custom Search API 的步驟：

### 步驟 1：前往 Google Custom Search 網站
- 進入 [Google Custom Search](https://cse.google.com/cse/).

### 步驟 2：創建新的 Custom Search 引擎
- 點擊 “Create a custom search engine” 按鈕。
- 輸入您希望搜索的網站或網域（例如，如果您只想搜索 Dcard，可以輸入 `https://www.dcard.tw/`）。
- 完成設定後，點擊 “Create” 按鈕來創建搜尋引擎。

### 步驟 3：啟用 Custom Search API
- 進入 [Google Cloud Console](https://console.cloud.google.com/)。
- 點擊左上角的選單並選擇 “API 和服務” > “庫”。
- 搜尋並選擇 "Custom Search API" 並啟用它。

### 步驟 4：創建 API 金鑰
- 在 Google Cloud Console 中，前往 “API 和服務” > “憑證” > “創建憑證” > “API 金鑰”。
- 複製您的 API 金鑰並保存在安全的地方。

### 步驟 5：設定搜尋引擎 ID（CX）
- 回到 [Google Custom Search Console](https://cse.google.com/cse/) 頁面，點選您的搜尋引擎並複製 "Search engine ID"（CX）。

### 步驟 6：使用 API
- 使用您獲得的 API 金鑰和 Search Engine ID（CX）來進行搜尋。
- 詳細文檔可參考 [Custom Search API Documentation](https://developers.google.com/custom-search/v1/overview)。
