#!/bin/bash
# CMA 유물 수집 → 임베딩 생성 → 키워드 태깅 파이프라인
# cron: 0 6 * * * /path/to/project/scripts/collect_pipeline.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python}"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/collect_pipeline_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 시작" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 1/3 collect_artworks" >> "$LOG_FILE"
$PYTHON manage.py collect_artworks >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 2/3 generate_embeddings" >> "$LOG_FILE"
$PYTHON manage.py generate_embeddings >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 3/3 map_keywords" >> "$LOG_FILE"
$PYTHON manage.py map_keywords >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 완료" >> "$LOG_FILE"
