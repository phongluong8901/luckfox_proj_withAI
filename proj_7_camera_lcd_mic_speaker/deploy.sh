#!/usr/bin/env bash
set -euo pipefail

LUCKFOX_IP="${1:-192.168.1.3}"
LUCKFOX_USER="${2:-root}"
REMOTE_DIR="/root/npu_rt"
LOG_FILE="${REMOTE_DIR}/node.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUCKFOX_SRC="${SCRIPT_DIR}/luckfox"

LUCKFOX_FILES=(
  "main_node.py"
  "shared_state.py"
  "gemini_client.py"
  "cacert.pem"
  "tcp_receiver.py"
  "npu_pipeline.py"
  "face_store.py"
  "tft_display.py"
  "audio_io.py"
  "voice_agent.py"
  "web_server.py"
  "index.html"
  "S99luckfox_bot"
)

LOCAL_YOLO="${SCRIPT_DIR}/colab/yolov8n.rknn"
LOCAL_DET="${SCRIPT_DIR}/colab/RetinaFace.rknn"
LOCAL_REC="${SCRIPT_DIR}/colab/MobileFaceNet.rknn"
LOCAL_BIN="${SCRIPT_DIR}/colab/rknn_vision_daemon"
LOCAL_FALLBACK_BIN="${SCRIPT_DIR}/colab/rknn_yolo_daemon"

for f in "${LUCKFOX_FILES[@]}"; do
  if [ ! -f "${LUCKFOX_SRC}/${f}" ]; then
    echo "[X] Khong tim thay ${LUCKFOX_SRC}/${f}"
    exit 1
  fi
done
if [ ! -f "${LOCAL_YOLO}" ]; then
  echo "[X] Khong tim thay ${LOCAL_YOLO}"
  exit 1
fi
BIN_TO_SEND=""
if [ -f "${LOCAL_BIN}" ]; then
  BIN_TO_SEND="${LOCAL_BIN}"
elif [ -f "${LOCAL_FALLBACK_BIN}" ]; then
  BIN_TO_SEND="${LOCAL_FALLBACK_BIN}"
else
  echo "[X] Khong tim thay binary rknn_vision_daemon hoac rknn_yolo_daemon trong colab/"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

SCP_LIST=()
for f in "${LUCKFOX_FILES[@]}"; do
  tr -d '\r' < "${LUCKFOX_SRC}/${f}" > "${TMP_DIR}/${f}"
  SCP_LIST+=("${TMP_DIR}/${f}")
done
SCP_LIST+=("${LOCAL_YOLO}" "${BIN_TO_SEND}")
for extra in "${LOCAL_DET}" "${LOCAL_REC}"; do
  if [ -f "${extra}" ]; then
    SCP_LIST+=("${extra}")
  fi
done

echo "[1/3] Don tien trinh cu tren ${LUCKFOX_USER}@${LUCKFOX_IP}..."
ssh "${LUCKFOX_USER}@${LUCKFOX_IP}" "mkdir -p '${REMOTE_DIR}/wav' && pkill -9 -f '[m]ain_node.py' 2>/dev/null || true; pkill -9 -f '[l]uckfox_vision_node.py' 2>/dev/null || true; pkill -9 -f '[r]knn_vision_daemon' 2>/dev/null || true; pkill -9 -f '[r]knn_yolo_daemon' 2>/dev/null || true"

echo "[2/3] Day code luckfox, model, binary, .env va wav sang ${REMOTE_DIR}..."
scp "${SCP_LIST[@]}" "${LUCKFOX_USER}@${LUCKFOX_IP}:${REMOTE_DIR}/"
if [ -f "${SCRIPT_DIR}/.env" ]; then
  tr -d '\r' < "${SCRIPT_DIR}/.env" > "${TMP_DIR}/.env"
  scp "${TMP_DIR}/.env" "${LUCKFOX_USER}@${LUCKFOX_IP}:${REMOTE_DIR}/.env"
fi
if [ -d "${SCRIPT_DIR}/assets/wav" ] && compgen -G "${SCRIPT_DIR}/assets/wav/*.wav" >/dev/null; then
  scp "${SCRIPT_DIR}/assets/wav/"*.wav "${LUCKFOX_USER}@${LUCKFOX_IP}:${REMOTE_DIR}/wav/"
fi

echo "[3/3] Khoi chay main_node.py..."
NOW_STR="$(date -u '+%Y-%m-%d %H:%M:%S')"
ssh "${LUCKFOX_USER}@${LUCKFOX_IP}" "
  date -u -s '${NOW_STR}' >/dev/null 2>&1 || true
  cp '${REMOTE_DIR}/S99luckfox_bot' /etc/init.d/S99luckfox_bot 2>/dev/null && chmod +x /etc/init.d/S99luckfox_bot 2>/dev/null || true
  chmod +x '${REMOTE_DIR}/main_node.py' '${REMOTE_DIR}/rknn_vision_daemon' '${REMOTE_DIR}/rknn_yolo_daemon' 2>/dev/null || true
  export LD_LIBRARY_PATH='/oem/usr/lib:/usr/lib:/lib:\${LD_LIBRARY_PATH:-}'
  cd '${REMOTE_DIR}'
  nohup python3 '${REMOTE_DIR}/main_node.py' > '${LOG_FILE}' 2>&1 < /dev/null &
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