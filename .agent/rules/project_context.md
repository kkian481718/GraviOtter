# 專案環境與狀態認知 (Project Context)

本專案是一個負責協助人類主人在手機或其他裝置上遙控各種底層工具（主要是 `Antigravity` Agent 等）的 **Discord Bot** (`GraviOtter` / 小水獺)。

## 系統環境與架構指示
1. **運行環境**: 目前託管於 GitHub Codespaces，但未來可能會轉移至一般免費 VPS，請避免依賴特殊的 Codespace 限制。
2. **開發語言**: Python 3 (主要使用 `discord.py`)，核心邏輯統一在 `main.py` 內。
3. **程序管理**: 專案由 PM2 背景駐留運行。如果修改了 `main.py`，你 **必須提醒使用者或透過指令重啟 PM2 (例如 `pm2 restart GraviOtter`)** 才能使改動生效。

## 開發與修改注意事項
- **Discord 限制**: 單條訊息字數上限為 2000 字，且有嚴格的 Rate Limits (每 5 秒不適合編輯或發送超過 5 次)。在實作任何 stdout/stderr 捕捉或回傳時，務必引入緩衝 (buffer) / 截斷，或是節流 (debounce) 機制。
- **指令分流**: Bot 主要處理兩件事：第一是自然對話，第二是執行特定指令 (`!run`, `!sys`, `!agent` 等)。在修改路由邏輯時請保持其職責分離。
