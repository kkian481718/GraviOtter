#!/bin/bash
exec > >(tee -a deploy-debug.log) 2>&1
echo "--- Starting post-start.sh at $(date) ---"

git pull
pip install -r requirements.txt

echo "Checking environment..."
pwd
ls -la main.py
python3 --version

echo "Launching background loop..."
nohup bash -c 'while true; do echo "[$(date)] Starting python3..."; python3 -u main.py; echo "[$(date)] Bot crashed/exited. Restarting in 3 sec..."; sleep 3; done' > bot.log 2>&1 < /dev/null &

echo "Background job launched. Current jobs:"
jobs -l
echo "--- post-start.sh finished ---"
