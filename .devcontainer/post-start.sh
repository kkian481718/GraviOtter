#!/bin/bash
echo "--- Starting post-start.sh at $(date) ---" >> deploy-debug.log

# 拉下最新程式碼
git pull >> deploy-debug.log 2>&1

echo "Starting bot with nohup..." >> deploy-debug.log

PIDFILE=".graviotter.pid"

if [ -f "$PIDFILE" ]; then
	OLDPID=$(cat "$PIDFILE")
	if ps -p $OLDPID >/dev/null 2>&1; then
		echo "Killing old PID $OLDPID" >> deploy-debug.log 2>&1
		kill $OLDPID >> deploy-debug.log 2>&1 || true
	fi
	rm -f "$PIDFILE"
fi

nohup python3 main.py >> deploy-debug.log 2>&1 &
echo $! > .graviotter.pid
echo "Started main.py with PID $(cat .graviotter.pid)" >> deploy-debug.log

echo "--- post-start.sh finished ---" >> deploy-debug.log
