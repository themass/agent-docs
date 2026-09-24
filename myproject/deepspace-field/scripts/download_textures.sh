#!/usr/bin/env bash
# Download planet textures into public/textures/ (fixes WebGL CORS from external CDNs).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/public/textures"
SSS="https://www.solarsystemscope.com/textures/download"

mkdir -p "$OUT"

files=(
  2k_sun.jpg
  2k_mercury.jpg
  2k_venus_atmosphere.jpg
  2k_earth_daymap.jpg
  2k_earth_clouds.jpg
  2k_moon.jpg
  2k_mars.jpg
  2k_jupiter.jpg
  2k_saturn.jpg
  2k_uranus.jpg
  2k_neptune.jpg
)

for f in "${files[@]}"; do
  echo "→ $f"
  curl -fsSL -o "$OUT/$f" "$SSS/$f"
done

echo "→ 2k_saturn_ring_alpha.png"
curl -fsSL -o "$OUT/2k_saturn_ring_alpha.png" "$SSS/2k_saturn_ring_alpha.png"

echo "→ moon_1024.jpg"
curl -fsSL -o "$OUT/moon_1024.jpg" \
  "https://threejs.org/examples/textures/planets/moon_1024.jpg"

echo "Done. $(du -sh "$OUT" | cut -f1) in $OUT"
