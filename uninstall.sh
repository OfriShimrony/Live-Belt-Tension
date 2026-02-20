#!/bin/bash
# Live Belt Tension Tuner - Uninstall Script

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

KLIPPER_CONFIG_PATH="${HOME}/printer_data/config"
MOONRAKER_CONFIG="${KLIPPER_CONFIG_PATH}/moonraker.conf"
MOONRAKER_COMPONENTS="${HOME}/moonraker/moonraker/components"
MAINSAIL_PATH="${HOME}/mainsail"
KLIPPERSCREEN_PATH="${HOME}/KlipperScreen"

print_msg()     { echo -e "${GREEN}[Live Belt Tuner]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

echo ""
echo "======================================================================"
echo " Live Belt Tension Tuner - Uninstall"
echo "======================================================================"
echo ""

# Moonraker component
if [ -f "${MOONRAKER_COMPONENTS}/belt_tuner.py" ]; then
    rm "${MOONRAKER_COMPONENTS}/belt_tuner.py"
    print_msg "Removed Moonraker component"
else
    print_warning "Moonraker component not found — skipping"
fi

# Mainsail web panel
if [ -f "${MAINSAIL_PATH}/belt_tuner.html" ]; then
    rm "${MAINSAIL_PATH}/belt_tuner.html"
    print_msg "Removed Mainsail web panel"
else
    print_warning "Mainsail web panel not found — skipping"
fi

# KlipperScreen panel
if [ -f "${KLIPPERSCREEN_PATH}/panels/belt_tuner_panel.py" ]; then
    rm "${KLIPPERSCREEN_PATH}/panels/belt_tuner_panel.py"
    print_msg "Removed KlipperScreen panel"
else
    print_warning "KlipperScreen panel not found — skipping"
fi

# Klipper macros
if [ -f "${KLIPPER_CONFIG_PATH}/belt_tuner_macros_simple.cfg" ]; then
    rm "${KLIPPER_CONFIG_PATH}/belt_tuner_macros_simple.cfg"
    print_msg "Removed Klipper macros"
else
    print_warning "Klipper macros not found — skipping"
fi

# moonraker.conf — remove [belt_tuner] and [update_manager live_belt_tension]
if [ -f "$MOONRAKER_CONFIG" ]; then
    # Remove [belt_tuner] block (single-line section with no keys)
    sed -i '/^\[belt_tuner\]/d' "$MOONRAKER_CONFIG"

    # Remove [update_manager live_belt_tension] block (multi-line)
    sed -i '/^\[update_manager live_belt_tension\]/,/^$/d' "$MOONRAKER_CONFIG"

    print_msg "Removed entries from moonraker.conf"
fi

echo ""
print_msg "Uninstall complete."
print_msg "Restart services to apply:"
print_msg "  sudo systemctl restart moonraker"
print_msg "  sudo systemctl restart klipper"
print_msg "  sudo systemctl restart KlipperScreen  # if installed"
echo ""
echo "Note: ~/Live-Belt-Tension repo was NOT removed."
echo "      To fully remove: rm -rf ~/Live-Belt-Tension"
echo ""
