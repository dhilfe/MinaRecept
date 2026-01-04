#!/usr/bin/env bash
set -euo pipefail

cd /home/bgp4/MinaRecept

git fetch origin
git checkout stage
git reset --hard origin/stage

docker compose up -d --build


