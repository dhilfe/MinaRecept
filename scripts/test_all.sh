#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
	PY="$ROOT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
	PY="python3"
elif command -v python >/dev/null 2>&1; then
	PY="python"
else
	echo "ERROR: No Python interpreter found (expected venv/bin/python, python3, or python)" >&2
	exit 1
fi

cd "$ROOT_DIR"

echo "==> Running unit tests"
"$PY" manage.py test --exclude-tag=e2e

echo "==> Running E2E tests (Playwright)"
"$PY" manage.py test --tag=e2e

if [[ "$(uname)" == "Darwin" ]] && command -v xcodebuild >/dev/null 2>&1 && command -v xcodegen >/dev/null 2>&1; then
	echo "==> Running iOS unit tests (XCTest)"
	(
		cd ios
		xcodegen generate

		if [[ -n "${IOS_TEST_DESTINATION:-}" ]]; then
			DESTINATION="$IOS_TEST_DESTINATION"
		else
			DEST_LINE="$(xcodebuild -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -showdestinations | grep -E 'platform:iOS Simulator' | grep -E 'name:iPhone' | head -n 1 || true)"
			if [[ -z "$DEST_LINE" ]]; then
				echo "==> Skipping iOS unit tests (no iPhone Simulator available)"
				exit 0
			fi
			DEST_OS="$(echo "$DEST_LINE" | sed -E 's/.*OS:([^,}]+).*/\1/')"
			DEST_NAME="$(echo "$DEST_LINE" | sed -E 's/.*name:([^}]+).*/\1/' | xargs)"
			DESTINATION="platform=iOS Simulator,name=$DEST_NAME,OS=$DEST_OS"
		fi

			LOG_FILE="$(mktemp)"
			set +e
			set +o pipefail
			if command -v xcpretty >/dev/null 2>&1; then
				xcodebuild test -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -destination "$DESTINATION" 2>&1 | tee "$LOG_FILE" | xcpretty
				STATUS=${PIPESTATUS[0]}
			else
				xcodebuild test -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -destination "$DESTINATION" 2>&1 | tee "$LOG_FILE"
				STATUS=${PIPESTATUS[0]}
			fi
			set -o pipefail
			set -e

			if [[ $STATUS -ne 0 ]]; then
				if grep -q "Scheme ReceptAppiOS is not currently configured for the test action" "$LOG_FILE"; then
					echo "==> No iOS tests configured for scheme; running build instead"
					if command -v xcpretty >/dev/null 2>&1; then
						xcodebuild build -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -destination "$DESTINATION" | xcpretty
					else
						xcodebuild build -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -destination "$DESTINATION"
					fi
				else
					rm -f "$LOG_FILE"
					exit $STATUS
				fi
			fi
			rm -f "$LOG_FILE"
	)
else
	echo "==> Skipping iOS unit tests (requires macOS + xcodebuild + xcodegen)"
fi

echo "All tests passed."
