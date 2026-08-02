#!/bin/bash
pip install -r requirements.txt

# 使用迴圈讓小水獺掛掉或收到 !restart 指令時可以自動重啟
nohup bash -c 'while true; do python3 main.py; echo "Bot crashed or restarted, restarting in 3 seconds..."; sleep 3; done' > bot.log 2>&1 &

