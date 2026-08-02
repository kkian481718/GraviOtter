---
trigger: always_on
---

# 專案環境與狀態認知 (Project Context)

本專案是一個負責協助人類主人在手機或其他裝置上遙控`Antigravity` Agent的 **Discord Bot** (`GraviOtter` / 小水獺)。

## 系統環境與架構指示
1. **運行環境**: 託管於 GitHub Codespaces，主要由使用者透過 iOS 捷徑呼叫 API 動態喚起。
2. **開發語言**: Python 3 (主要使用 `discord.py`)，核心邏輯統一在 `main.py` 內。
3. **程序管理**: 專案依賴 `.devcontainer/post-start.sh` 裡的 `while true` 迴圈背景常駐運行。如果修改了 `main.py`，請善用機器人的 `!restart` 指令（內部會呼叫 `await bot.close()` 並由外部腳本自動重啟）來讓改動生效。

## 開發與修改注意事項
- **Discord 限制**: 單條訊息字數上限為 2000 字，且有嚴格的 Rate Limits (每 5 秒不適合編輯或發送超過 5 次)。在實作任何 stdout/stderr 捕捉或回傳時，務必引入緩衝 (buffer) / 截斷，或是節流 (debounce) 機制。
- **指令分流**: Bot 主要處理兩件事：第一是自然對話，第二是執行特定指令 (`!run`, `!sys`, `!agent` 等)。在修改路由邏輯時請保持其職責分離。
- **文件規範**: 請盡量不要主動產生或維護過多系統說明文件，因為版本更新頻繁容易導致文件內容過時，保持輕量即可。
