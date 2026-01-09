#!/usr/bin/env bash
set -euo pipefail

cd /home/bgp4/MinaRecept

git fetch origin
git checkout stage
git reset --hard origin/stage

export GIT_SHA="$(git rev-parse --short HEAD)"
echo "[deploy_stage] Deploying stage @ ${GIT_SHA}"

docker compose up -d --build
