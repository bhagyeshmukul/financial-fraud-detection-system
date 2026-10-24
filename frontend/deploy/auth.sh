#!/bin/sh
# Generate the private gateway password hash at startup rather than image build time.
set -eu
: "${ANALYST_USER:?Set ANALYST_USER for the private web gateway}"
: "${ANALYST_PASSWORD:?Set ANALYST_PASSWORD for the private web gateway}"
: "${API_ACCESS_TOKEN:?Set API_ACCESS_TOKEN for backend authentication}"
if [ "${#ANALYST_PASSWORD}" -lt 12 ] || [ "${#API_ACCESS_TOKEN}" -lt 32 ]; then
  echo "Use at least 12 characters for ANALYST_PASSWORD and 32 for API_ACCESS_TOKEN." >&2
  exit 1
fi
# Token is interpolated into an Nginx config: accept only a safe generated alphabet.
case "$API_ACCESS_TOKEN" in *[!a-zA-Z0-9_-]*) echo "API_ACCESS_TOKEN must be URL-safe alphanumeric." >&2; exit 1;; esac
printf '%s\n' "$ANALYST_PASSWORD" | htpasswd -iBc /tmp/fraud.htpasswd "$ANALYST_USER"
