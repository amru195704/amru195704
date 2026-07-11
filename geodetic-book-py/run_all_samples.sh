#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -n "${PYTHON:-}" ]]; then
  python_cmd="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "Python interpreter not found. Set PYTHON or install python3." >&2
  exit 1
fi

scripts=(
  "ch03/ch03_make_test_par.py"
  "ch01/ch01_degree_length.py"
  "ch01/ch01_ellipsoid.py"
  "ch01/ch01_gauss_krueger.py"
  "ch01/ch01_meridian_arc.py"
  "ch02/ch02_helmert.py"
  "ch02/ch02_xyz_blh.py"
  "ch03/ch03_par_reader.py"
  "ch03/ch03_bilinear.py"
  "ch04/ch04_inverse_iter.py"
  "ch05/ch05_geoid.py"
  "ch05/ch05_height.py"
  "ch06/ch06_sequential.py"
  "ch07/ch07_boundary.py"
  "ch08/ch08_verify.py"
  "ch09/ch09_par2sqlite.py"
  "ch10/ch10_heatmap.py"
)

echo "Using Python: $python_cmd"
echo "Base directory: $SCRIPT_DIR"

for script in "${scripts[@]}"; do
  echo
  echo ">>> Running $script"
  "$python_cmd" "$SCRIPT_DIR/$script"
done

echo
echo "Completed ${#scripts[@]} scripts successfully."