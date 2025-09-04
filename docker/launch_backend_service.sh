#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to load environment variables from .env file
load_env_file() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local env_file="$script_dir/../.env"

    if [ -f "$env_file" ]; then
        echo "Loading environment variables from: $env_file"
        set -a
        (source "$env_file")
        set +a
    else
        echo "Warning: .env file not found at: $env_file"
    fi
}

load_env_file

export http_proxy=""; export https_proxy=""; export no_proxy=""; export HTTP_PROXY=""; export HTTPS_PROXY=""; export NO_PROXY=""
export PYTHONPATH=$(pwd)

export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/
JEMALLOC_PATH=$(pkg-config --variable=libdir jemalloc)/libjemalloc.so 2>/dev/null || JEMALLOC_PATH=""

PY=python3

if [[ -z "$WS" || $WS -lt 1 ]]; then
  WS=1
fi

MAX_RETRIES=5
STOP=false
PIDS=()
export NLTK_DATA="./nltk_data"

cleanup() {
  echo "Termination signal received. Shutting down..."
  STOP=true
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "Killing process $pid"
      kill "$pid"
    fi
  done
  exit 0
}

trap cleanup SIGINT SIGTERM

task_exe(){
    local task_id=$1
    local retry_count=0
    while ! $STOP && [ $retry_count -lt $MAX_RETRIES ]; do
        echo "Starting task_executor.py for task $task_id (Attempt $((retry_count+1)))"
        LD_PRELOAD=$JEMALLOC_PATH $PY rag/svr/task_executor.py "$task_id"
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 0 ]; then
            echo "task_executor.py for task $task_id exited successfully."
            break
        else
            echo "task_executor.py for task $task_id failed with exit code $EXIT_CODE. Retrying..." >&2
            retry_count=$((retry_count + 1))
            sleep 2
        fi
    done

    if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "task_executor.py for task $task_id failed after $MAX_RETRIES attempts. Exiting..." >&2
        cleanup
    fi
}

run_server(){
    local retry_count=0
    while ! $STOP && [ $retry_count -lt $MAX_RETRIES ]; do
        echo "Starting ragflow_server.py (Attempt $((retry_count+1)))"
        $PY api/ragflow_server.py
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 0 ]; then
            echo "ragflow_server.py exited successfully."
            break
        else
            echo "ragflow_server.py failed with exit code $EXIT_CODE. Retrying..." >&2
            retry_count=$((retry_count + 1))
            sleep 2
        fi
    done

    if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "ragflow_server.py failed after $MAX_RETRIES attempts. Exiting..." >&2
        cleanup
    fi
}

# -----------------------------------------------------------------
# [删除] 移除了 run_mock_crawl4ai_server 函数
# -----------------------------------------------------------------

# Start task executors
for ((i=0;i<WS;i++))
do
  task_exe "$i" &
  PIDS+=($!)
done

# -----------------------------------------------------------------
# [删除] 移除了启动 mock_crawl4ai_server 的命令
# -----------------------------------------------------------------

# Start the main RAGFlow server
run_server &
PIDS+=($!)

wait