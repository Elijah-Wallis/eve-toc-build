#!/bin/zsh
# THE NUCLEAR OPTION: macOS Native MoltBot Installer
set -e

# --- CONFIGURATION ---
NEW_LLM_KEY="sk-emergent-80845B34f5fD8A0A21"
RESTIC_REPO="s3:s3.amazonaws.com/moltbot-emergent/molt-310126-2"
INSTALL_BASE="$HOME/moltbot"
APP_DIR="$INSTALL_BASE/app"
CONFIG_DIR="$HOME/.clawdbot"
LAUNCH_LABEL="com.emergent.moltbot"
PLIST_PATH="$HOME/Library/LaunchAgents/${LAUNCH_LABEL}.plist"

echo "☢️  INITIATING NUCLEAR INSTALLATION..."

# 1. INSTALL NATIVE DEPENDENCIES
echo "📦 Checking System Dependencies..."
if ! command -v brew &> /dev/null; then
    echo "❌ Error: Homebrew is required. Install it first."
    exit 1
fi
brew list restic &>/dev/null || brew install restic
brew list node &>/dev/null || brew install node
brew list mongodb-community &>/dev/null || brew install mongodb-community

# 2. START DATABASE
echo "🗄️  Starting MongoDB..."
brew services start mongodb-community
sleep 3

# 3. RESTORE AGENT SNAPSHOT
echo "⬇️  Restoring Agent Snapshot from S3..."
rm -rf "$INSTALL_BASE"
mkdir -p "$INSTALL_BASE"
export RESTIC_REPOSITORY="$RESTIC_REPO"
export RESTIC_PASSWORD="" 
restic -o s3.unsafe-anonymous-auth=true --insecure-no-password --no-lock restore latest \
    --target "$INSTALL_BASE" \
    --exclude "/data/db" \
    --exclude "/var" \
    --exclude "/etc" \
    --exclude "/dev" || { echo "❌ Restore failed"; exit 1; }

echo "✅ Snapshot restored."

# 4. PATCH CONFIGURATION
echo "🔧 Patching Configuration & Injecting Keys..."
mkdir -p "$CONFIG_DIR"
if [ -d "$INSTALL_BASE/root/.clawdbot" ]; then
    cp -Rn "$INSTALL_BASE/root/.clawdbot/" "$CONFIG_DIR/"
fi

CONFIG_FILES=(
    "$APP_DIR/backend/.env"
    "$CONFIG_DIR/clawdbot.json"
    "$CONFIG_DIR/moltbot.json"
    "$CONFIG_DIR/agents/main/agent/models.json"
    "$APP_DIR/frontend/.env"
)
BACKEND_URL="http://localhost:8000"

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        sed -i '' -E "s|sk-emergent-[a-zA-Z0-9]+|$NEW_LLM_KEY|g" "$file"
        sed -i '' -E "s|https://[a-zA-Z0-9-]*\.preview\.emergentagent\.com|$BACKEND_URL|g" "$file"
        sed -i '' -E "s|/app|$APP_DIR|g" "$file"
    fi
done

# 5. REBUILD APPLICATION (Apple Silicon)
echo "🏗️  Rebuilding Backend..."
if [ -d "$APP_DIR/backend" ]; then
    cd "$APP_DIR/backend"
    rm -rf node_modules
    npm install --silent --no-audit
fi

echo "🏗️  Rebuilding Frontend..."
if [ -d "$APP_DIR/frontend" ]; then
    cd "$APP_DIR/frontend"
    rm -rf node_modules
    npm install --silent --no-audit
    npm run build
fi

# 6. NATIVE PERSISTENCE (Launchd)
echo "🚀 Creating LaunchAgent..."
NODE_BIN=$(which node)
cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LAUNCH_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$NODE_BIN</string>
        <string>index.js</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$APP_DIR/backend</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEW_LLM_KEY</key>
        <string>$NEW_LLM_KEY</string>
        <key>NODE_ENV</key>
        <string>production</string>
        <key>PORT</key>
        <string>8000</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_BASE/moltbot.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_BASE/moltbot.err</string>
</dict>
</plist>
EOF

# 7. LAUNCH
echo "🔥 Igniting Service..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"

echo "=== INSTALLATION COMPLETE ==="
echo "   - Agent Status: Running ($LAUNCH_LABEL)"
echo "   - Logs:         tail -f $INSTALL_BASE/moltbot.log"
