#!/usr/bin/env bash
# Build build/Sotto.app: release binary, Info.plist, icon, code signature.
#   SIGN_IDENTITY="Developer ID Application: ..." ./build-app.sh   (default: first Apple Development identity, else ad-hoc)
#   BUNDLE_ID=com.example.sotto ./build-app.sh
set -euo pipefail
cd "$(dirname "$0")"
BUNDLE_ID=${BUNDLE_ID:-dev.sotto.Sotto}
VERSION=${VERSION:-0.0.1}
APP=build/Sotto.app

swift build -c release
rm -rf "$APP" build/icon.iconset
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/icon.iconset
cp .build/release/Sotto "$APP/Contents/MacOS/Sotto"
"$APP/Contents/MacOS/Sotto" --icon build/icon.iconset
iconutil -c icns build/icon.iconset -o "$APP/Contents/Resources/Sotto.icns"
# Claude and Anthropic logos (see Brand/NOTICE.md).
if compgen -G "Brand/*.png" >/dev/null; then cp Brand/*.png "$APP/Contents/Resources/"; fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Sotto</string>
  <key>CFBundleDisplayName</key><string>sotto</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleExecutable</key><string>Sotto</string>
  <key>CFBundleIconFile</key><string>Sotto</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

IDENTITY=${SIGN_IDENTITY:-$(security find-identity -v -p codesigning | awk -F'"' '/Apple Development|Developer ID Application/ {print $2; exit}')}
if [ -n "$IDENTITY" ]; then
  codesign --force --options runtime --sign "$IDENTITY" "$APP"
else
  echo "no signing identity found; signing ad-hoc" >&2
  codesign --force --sign - "$APP"
fi
codesign --verify --strict "$APP"
echo "built $APP, signed by: $(codesign -dv --verbose=2 "$APP" 2>&1 | awk -F= '/^Authority/ {print $2; exit}')"
