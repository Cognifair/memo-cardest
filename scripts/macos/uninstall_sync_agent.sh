#!/bin/sh
set -eu
LABEL="com.cognifair.memocardest.sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed LaunchAgent: $PLIST"
