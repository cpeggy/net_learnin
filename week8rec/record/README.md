- 問題說明
  - 明確說明本專題要解決的問題或需求是什麼
- 前期提要：我待在一間做線上課程的公司上班，是課程產品實習生，需要協助課程產品經理各種事。
- My Main Proj.
  - 同事在進行開課前的市場調查後要設計課程 Detail Page、行銷企劃、影音企劃等很難完全站在 TA 的角度看待設計的企劃或文案是否能打中 TA 並使他願意購買課程
  - 尤其不熟悉的領域更是困難（站在 TA 的視角這件事），開賣後發現企劃的效果差的修改成本會影響課程營收
  - 目前的 AI Persona 工具開始使用時需要定義商業模式......等等，但我們手上只有問卷結果與訪談紀錄，沒有特定商業模式
  - 有些要收費，但在不確定好不好用前課金好像哪裡怪怪的（無論是自己課金還是公司買）
  - 所以想做這個 AI Persona 工具
  - 從問卷結果、訪談紀錄利用 Prompt 將這些資料給 Gemini API，整裡後回傳整裡完的 Persona
  - 再選擇合適的 Persona 去詢問 文案/企劃 是否有打中（讓他們願意購買）
- Branch Proj.
  - 在開課前除了問卷調查與訪談了解 TA 外，也會用輿情分析去調查 TA 們在討論什麼
  - 輿情分析是一件超級耗時且燒腦的工作與過程
  - 所以製作一個對語言學習特定學習者的輿情調查工具
  - 連結 Google Custom Search API 來搜尋輿情（大家討論什麼）
  - 搜尋到的結果根據標題進行分類（語法問題、發音問題、聽力問題、詞彙問題、文化理解問題、口說練習、語言學習技巧）
    - 這部分頁可以客製化讓大家自由修改分類
  - 分類後再製成圖表看大家討論哪一類比較多
