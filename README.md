# GraviOtter (小水獺)

My assistant for on-phone coding & remote agent control.

## Project Overview (專案概述)
這個專案是一個掛載在 **GitHub Codespaces** 上，並由 **PM2** 管理常駐執行的 **Discord Bot**。
主要目的是作為橋樑，讓使用者能透過 Discord (dc) 遠端遙控 **Antigravity AI Agent**，從手機或任何裝置免費且方便地使用尖端模型。

## System Setup (系統架構)
- **環境介面**: GitHub Codespaces
- **程序管理**: PM2 (確保 Bot 穩定在背景運行)
- **互動介面**: Discord Bot (監聽訊息、發送對話)
- **核心大腦**: Antigravity (負責處理複雜的請求與回應)

## Future Feature: API Quota Proactive Warning (API 用量主動提醒機制)
**給未來的 Agent (To Future Agents):**
未來在擴充此專案時，需要實作一個追蹤 API 用量的功能：
1. **用量追蹤**: 在每次呼叫模型 API 後，擷取並記錄已消耗的 Tokens 數。
2. **主動推播**: 當累計用量快達到上限（如 80% 或 90%）時，透過 Discord Bot API 主動發送私訊 (DM) 給使用者。
3. **角色設定**: 請以「小水獺 (GraviOtter)」的口吻發送警告。例如：「主人，我的體力快被榨乾啦... 今天的 API 額度快滿了，請注意喔 🦦」
