#!/bin/sh
cd "$(dirname "$0")" || exit 1
printf 'AlphaScope — open http://127.0.0.1:8765 after the server starts.\n'
exec python3 server.py --port 8765
