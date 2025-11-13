#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC2034
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIXTURE_ROOT="${PROJECT_ROOT}/rexlit/docs/idl-fixtures"

echo "=== RexLit IDL Fixture Setup ==="
echo "Project root: ${PROJECT_ROOT}"
echo "Fixture root: ${FIXTURE_ROOT}"
echo

python - <<'PY' || {
    cat <<'EOF'
[!] Missing optional dev dependencies for IDL fixture generation.
    Run: pip install 'rexlit[dev-idl]'
EOF
    exit 1
}
try:
    import chug  # noqa: F401
except ModuleNotFoundError as exc:  # pragma: no cover - developer helper
    raise SystemExit(str(exc))
PY

mkdir -p "${FIXTURE_ROOT}"

TIERS="${IDL_SETUP_TIERS:-small}"
SEED="${IDL_SETUP_SEED:-42}"

tiers_array=()
IFS=', ' read -r -a tiers_array <<< "${TIERS}"

if [ "${#tiers_array[@]}" -eq 0 ]; then
    echo "[!] No tiers specified. Set IDL_SETUP_TIERS (e.g. 'small,medium')."
    exit 1
fi

function tier_default_count() {
    case "$1" in
        small) echo 100 ;;
        medium) echo 1000 ;;
        large) echo 10000 ;;
        xl) echo 100000 ;;
        *) echo "${IDL_SETUP_COUNT:-0}" ;;
    esac
}

for tier in "${tiers_array[@]}"; do
    output_dir="${FIXTURE_ROOT}/${tier}"
    manifest="${output_dir}/manifest.jsonl"

    if [ -f "${manifest}" ]; then
        echo "[=] ${tier} corpus already exists (${manifest})"
        continue
    fi

    count="$(tier_default_count "${tier}")"
    if [ "${count}" -eq 0 ]; then
        echo "[!] Unknown tier '${tier}'. Provide IDL_SETUP_COUNT for custom tiers."
        exit 1
    fi

    echo "[+] Generating '${tier}' corpus (count=${count}, seed=${SEED})"
    python "${PROJECT_ROOT}/scripts/dev/idl_sample_docs.py" \
        --tier "${tier}" \
        --count "${count}" \
        --seed "${SEED}" \
        --output "${output_dir}" \
        --validate
done

echo
echo "=== Validating fixture integrity ==="
python "${PROJECT_ROOT}/scripts/validate_idl_fixtures.py" "${FIXTURE_ROOT}/"* 2>/tmp/idl-validate.err || true
cat /tmp/idl-validate.err
rm -f /tmp/idl-validate.err

echo
echo "=== Fixture Summary ==="
for tier_dir in "${FIXTURE_ROOT}"/*; do
    [ -d "${tier_dir}" ] || continue
    manifest="${tier_dir}/manifest.jsonl"
    if [ -f "${manifest}" ]; then
        count=$(wc -l < "${manifest}")
        printf "  %-12s %6d documents (%s)\n" "$(basename "${tier_dir}")" "${count}" "${manifest}"
    else
        printf "  %-12s (manifest missing)\n" "$(basename "${tier_dir}")"
    fi
done

echo
echo "Done. Export IDL_FIXTURE_PATH=${FIXTURE_ROOT} to point tests at these corpora."

