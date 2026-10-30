#!/usr/bin/env bash
set -euo pipefail
mkdir -p /data/hdfs/namenode
if [ ! -f /data/hdfs/namenode/current/VERSION ]; then
  echo '[SRAI] Formatage initial du NameNode (premier demarrage uniquement)'
  hdfs namenode -format -nonInteractive
fi
exec hdfs namenode
