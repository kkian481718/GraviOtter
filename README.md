# GraviOtter (小水獺)

My assistant for on-phone coding & remote agent control.

## Project Overview (專案概述)
這個專案是一個掛載在 **GitHub Codespaces** 上，並由 **PM2** 管理常駐執行的 **Discord Bot**。
主要目的是作為橋樑，讓使用者能透過 Discord (dc) 遠端遙控 **Antigravity AI Agent**，從手機或任何裝置免費且方便地使用尖端模型。

## System Setup (系統架構)
- **環境介面**: GitHub Codespaces (支援多種 VPS 部署)
- **程序管理**: PM2 (確保 Bot 穩定在背景運行)
- **互動介面**: Discord Bot (監聽訊息、發送對話)
- **核心大腦**: Antigravity / Gemini API

---

> ** 給未來 AI Agent 的開發提示 (To Future AI Agents)**
> 若需要了解本專案的底層技術限制、環境變數規範與 Discord API 的應對方式，請直接讀取本專案內的 `.agent/rules/project_context.md`，該處存有最新的專案上下文認知。
