#!/bin/bash
echo "--- post-create.sh started at $(date) ---" >> deploy-debug.log
echo "Installing Python dependencies..." >> deploy-debug.log

# 只安裝 Python 套件（使用 nohup 啟動，不需要 pm2）
if [ -f requirements.txt ]; then
	pip install -r requirements.txt >> deploy-debug.log 2>&1 || echo "pip install failed" >> deploy-debug.log
else
	echo "requirements.txt not found" >> deploy-debug.log
fi

echo "Initialization complete!" >> deploy-debug.log
echo "--- post-create.sh finished ---" >> deploy-debug.log
