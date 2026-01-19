#!/usr/bin/env bash
set -e

DEPLOYMENT=${1:-care-session-service}
REVISION=${2:-}

if [[ -z "$REVISION" ]]; then
  echo "Usage: $0 <deployment> <revision>"
  exit 1
fi

oc rollout undo deployment/$DEPLOYMENT --to-revision=$REVISION
oc rollout status deployment/$DEPLOYMENT
