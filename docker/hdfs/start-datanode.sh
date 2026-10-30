#!/usr/bin/env bash
set -euo pipefail
mkdir -p /data/hdfs/datanode
exec hdfs datanode
