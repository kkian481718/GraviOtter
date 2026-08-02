#!/bin/bash
echo "--- Starting post-start.sh at $(date) ---" > deploy-debug.log

# 啟動時先將遠端最新的程式碼拉下來
git pull >> deploy-debug.log 2>&1

# 使用 PM2 接管小水獺 (完全無視Codespace清除背景程序的限制)
echo "Starting Bot via PM2..." >> deploy-debug.log
pm2 start main.py --interpreter python3 --name graviotter >> deploy-debug.log 2>&1

echo "Current background services:" >> deploy-debug.log
pm2 status >> deploy-debug.log 2>&1

echo "--- post-start.sh finished ---" >> deploy-debug.log
