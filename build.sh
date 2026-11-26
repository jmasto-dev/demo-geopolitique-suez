#!/bin/sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-/home/devuser/lemo-opuscar}
export LIB
cd "$LIB"
"$LIB/.venv/bin/python" core/tts/tts_zh.py "$HERE/lines.json" "$HERE/voices/"
node core/render/events.mjs "$HERE"
"$LIB/.venv/bin/python" "$HERE/mix.py"
node core/render/video.mjs "$HERE" --fps 24 --workers 2 --out "$HERE/out/video.mp4"
sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/demo-geopolitique-suez.mp4" 24 0
node -e "
const fs = require('fs');
const durs = JSON.parse(fs.readFileSync('$HERE/voices/dur.json', 'utf8'));
const lines = JSON.parse(fs.readFileSync('$HERE/lines.json', 'utf8'));
const cues = lines.map(l => ({ t0: l.t, t1: +(l.t + durs[l.id] + 0.35).toFixed(3), text: l.text }));
fs.writeFileSync('$HERE/out/cues.json', JSON.stringify(cues, null, 2));
"
"$LIB/.venv/bin/python" core/render/srt.py "$HERE/out/cues.json" "$HERE/subtitles_fr.srt"
node core/render/readcheck.mjs "$HERE"
cp "$HERE/stills/t_16.5.jpg" "$HERE/poster.jpg"
