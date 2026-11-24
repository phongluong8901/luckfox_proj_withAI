#!/usr/bin/env bash
set -euo pipefail

LUCKFOX_IP="${1:-192.168.1.3}"
LUCKFOX_USER="${2:-root}"
REMOTE_DIR="/root/npu_rt"
LOG_FILE="${REMOTE_DIR}/node.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TEXT_FILES=(
  "luckfox_vision_node.py"
  "npu_worker.py"
  "web_server.py"
  "index.html"
)
LOCAL_MODEL="${SCRIPT_DIR}/colab/yolov8n.rknn"
LOCAL_BIN="${SCRIPT_DIR}/colab/rknn_yolo_daemon"

for f in "${TEXT_FILES[@]}"; do
  if [ ! -f "${SCRIPT_DIR}/${f}" ]; then
    echo "[X] Khong tim thay ${SCRIPT_DIR}/${f}"
    exit 1
  fi
done
for f in "${LOCAL_MODEL}" "${LOCAL_BIN}"; do
  if [ ! -f "${f}" ]; then
    echo "[X] Khong tim thay ${f}"
    exit 1
  fi
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT
SCP_LIST=()
for f in "${TEXT_FILES[@]}"; do
  tr -d '\r' < "${SCRIPT_DIR}/${f}" > "${TMP_DIR}/${f}"
  SCP_LIST+=("${TMP_DIR}/${f}")
done
SCP_LIST+=("${LOCAL_MODEL}" "${LOCAL_BIN}")

echo "[1/3] Tao thu muc va don tien trinh cu tren ${LUCKFOX_USER}@${LUCKFOX_IP}..."
ssh "${LUCKFOX_USER}@${LUCKFOX_IP}" "mkdir -p '${REMOTE_DIR}' && pkill -9 -f '[l]uckfox_vision_node.py' 2>/dev/null || true; pkill -9 -f '[r]knn_yolo_daemon' 2>/dev/null || true"

echo "[2/3] Day code, UI, model YOLO va binary sang ${REMOTE_DIR}..."
scp "${SCP_LIST[@]}" "${LUCKFOX_USER}@${LUCKFOX_IP}:${REMOTE_DIR}/"

echo "[3/3] Cap quyen va khoi chay server nen..."
ssh "${LUCKFOX_USER}@${LUCKFOX_IP}" "
  chmod +x '${REMOTE_DIR}/luckfox_vision_node.py' '${REMOTE_DIR}/rknn_yolo_daemon'
  export LD_LIBRARY_PATH='/oem/usr/lib:/usr/lib:/lib:\${LD_LIBRARY_PATH:-}'
  nohup python3 '${REMOTE_DIR}/luckfox_vision_node.py' > '${LOG_FILE}' 2>&1 < /dev/null &
  PID=\$!
  sleep 2
  if kill -0 \$PID 2>/dev/null; then
    echo '[OK] Server dang chay (PID='\$PID') -> http://${LUCKFOX_IP}:8080'
  else
    echo '[X] Server bi tat!'
  fi
  echo '--- LOG ---'
  cat '${LOG_FILE}' 2>/dev/null || true
"