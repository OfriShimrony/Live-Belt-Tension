#!/bin/bash
# Live Belt Tension Tuner - Installation Script
# Run this from the cloned repo directory or via:
#   bash <(curl -sSL https://raw.githubusercontent.com/OfriShimrony/Live-Belt-Tension/main/install.sh)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BELT_TUNER_PATH="${HOME}/Live-Belt-Tension"
KLIPPER_PATH="${HOME}/klipper"
KLIPPER_CONFIG_PATH="${HOME}/printer_data/config"
KLIPPERSCREEN_PATH="${HOME}/KlipperScreen"
MOONRAKER_CONFIG="${KLIPPER_CONFIG_PATH}/moonraker.conf"
REPO_URL="https://github.com/OfriShimrony/Live-Belt-Tension.git"

print_msg()     { echo -e "${GREEN}[Live Belt Tuner]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# ── 1. Prerequisites ───────────────────────────────────────────────────────────

check_klipper() {
    print_msg "Checking Klipper installation..."
    if [ ! -d "$KLIPPER_PATH" ]; then
        print_error "Klipper not found at $KLIPPER_PATH"
        exit 1
    fi
    print_msg "  Klipper found"
}

check_moonraker() {
    print_msg "Checking Moonraker..."
    if ! systemctl list-units --full -all 2>/dev/null | grep -q "moonraker.service"; then
        print_error "Moonraker service not found"
        exit 1
    fi
    print_msg "  Moonraker found"
}

check_gcode_shell_command() {
    print_msg "Checking gcode_shell_command extension..."
    local ext_path="${KLIPPER_PATH}/klippy/extras/gcode_shell_command.py"
    if [ ! -f "$ext_path" ]; then
        print_warning "  gcode_shell_command.py not found at $ext_path"
        print_warning "  Install it via KIAUH or manually:"
        print_warning "    https://github.com/dw-0/kiauh"
        print_warning "  Skipping — the macros in belt_tuner_macros.cfg require it."
        print_warning "  Use belt_tuner_macros_simple.cfg as an alternative (no extension needed)."
    else
        print_msg "  gcode_shell_command found"
    fi
}

check_accelerometer() {
    print_msg "Checking for ADXL345 in Klipper config..."
    if ! grep -r "adxl345" "${KLIPPER_CONFIG_PATH}"/*.cfg 2>/dev/null | grep -q .; then
        print_warning "  ADXL345 not found in config files"
        print_warning "  Make sure [adxl345] is configured in your printer.cfg"
    else
        print_msg "  ADXL345 configuration found"
    fi
}

# ── 2. Dependencies ────────────────────────────────────────────────────────────

install_dependencies() {
    print_msg "Installing Python dependencies (numpy, scipy)..."

    # Klipper virtualenv
    if [ -f "${HOME}/klippy-env/bin/pip" ]; then
        print_msg "  Installing into klippy-env..."
        "${HOME}/klippy-env/bin/pip" install -q numpy scipy || \
            print_warning "  klippy-env install failed, continuing..."
    fi

    # KlipperScreen virtualenv (separate env, needs its own numpy/scipy)
    for ks_env in "${HOME}/KlipperScreen/.venv" "${HOME}/.KlipperScreen-env"; do
        if [ -f "${ks_env}/bin/pip" ]; then
            print_msg "  Installing into KlipperScreen env (${ks_env})..."
            "${ks_env}/bin/pip" install -q numpy scipy || \
                print_warning "  KlipperScreen env install failed, continuing..."
            break
        fi
    done

    # System-level fallback
    print_msg "  Installing system packages as fallback..."
    sudo apt-get install -y python3-numpy python3-scipy 2>/dev/null || true

    print_msg "  Dependencies installed"
}

# ── 3. Clone / update repo ─────────────────────────────────────────────────────

clone_or_update() {
    print_msg "Setting up Live-Belt-Tension repository..."
    if [ -d "$BELT_TUNER_PATH/.git" ]; then
        print_msg "  Repository already exists — pulling latest..."
        git -C "$BELT_TUNER_PATH" pull
    else
        print_msg "  Cloning repository..."
        git clone "$REPO_URL" "$BELT_TUNER_PATH"
    fi
    print_msg "  Repository ready at $BELT_TUNER_PATH"
}

# ── 4. Klipper macros ─────────────────────────────────────────────────────────

install_macros() {
    print_msg "Installing Klipper macros..."
    if [ ! -d "$KLIPPER_CONFIG_PATH" ]; then
        print_warning "  Klipper config dir not found at $KLIPPER_CONFIG_PATH — skipping macro install"
        print_warning "  Copy gcode/belt_tuner_macros.cfg manually to your config folder"
        return
    fi

    cp "${BELT_TUNER_PATH}/gcode/belt_tuner_macros_simple.cfg" "${KLIPPER_CONFIG_PATH}/"
    print_msg "  Macros copied to $KLIPPER_CONFIG_PATH"
    print_msg "  Add this line to your printer.cfg to activate:"
    print_msg "    [include belt_tuner_macros_simple.cfg]"
}

# ── 5. KlipperScreen panel ────────────────────────────────────────────────────

install_klipperscreen_panel() {
    print_msg "Installing KlipperScreen panel..."
    if [ ! -d "$KLIPPERSCREEN_PATH" ]; then
        print_warning "  KlipperScreen not found at $KLIPPERSCREEN_PATH — skipping panel install"
        return
    fi

    local panels_dir="${KLIPPERSCREEN_PATH}/panels"
    local styles_dir="${KLIPPERSCREEN_PATH}/styles"

    if [ ! -d "$panels_dir" ]; then
        print_warning "  KlipperScreen panels directory not found — skipping panel install"
        return
    fi

    cp "${BELT_TUNER_PATH}/src/belt_tuner_panel.py" "${panels_dir}/"
    print_msg "  Panel installed to $panels_dir"

    if [ -d "$styles_dir" ] && [ -f "${BELT_TUNER_PATH}/src/belt_tuner.css" ]; then
        cp "${BELT_TUNER_PATH}/src/belt_tuner.css" "${styles_dir}/"
        print_msg "  CSS installed to $styles_dir"
    fi

    print_msg "  Add the panel to your KlipperScreen config:"
    print_msg "    [menu __main belt_tuner]"
    print_msg "    name: Belt Tuner"
    print_msg "    panel: belt_tuner_panel"
}

# ── 6. Moonraker update manager ───────────────────────────────────────────────

add_moonraker_config() {
    print_msg "Configuring Moonraker update manager..."
    if [ ! -f "$MOONRAKER_CONFIG" ]; then
        print_warning "  moonraker.conf not found — skipping update manager config"
        return
    fi

    if grep -q "\[update_manager live_belt_tension\]" "$MOONRAKER_CONFIG"; then
        print_msg "  Moonraker update manager already configured"
    else
        cat >> "$MOONRAKER_CONFIG" << EOF

[update_manager live_belt_tension]
type: git_repo
path: ~/Live-Belt-Tension
origin: ${REPO_URL}
primary_branch: main
managed_services: klipper
EOF
        print_msg "  Moonraker update manager configured"
    fi
}

# ── 7. Set permissions ────────────────────────────────────────────────────────

set_permissions() {
    print_msg "Setting permissions..."
    chmod +x "${BELT_TUNER_PATH}/src/"*.py 2>/dev/null || true
    print_msg "  Done"
}

# ── 8. Summary ────────────────────────────────────────────────────────────────

print_instructions() {
    echo ""
    echo "======================================================================"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "======================================================================"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Add to printer.cfg:"
    echo "       [include belt_tuner_macros_simple.cfg]"
    echo ""
    echo "  2. Restart Klipper:"
    echo "       sudo systemctl restart klipper"
    echo ""
    echo "  3. If you installed the KlipperScreen panel, restart KlipperScreen:"
    echo "       sudo systemctl restart KlipperScreen"
    echo ""
    echo "  4. Test the analyzer directly:"
    echo "       python3 ~/Live-Belt-Tension/src/belt_analyzer_v3.py <csv_file>"
    echo ""
    echo "  5. From the Klipper console:"
    echo "       BELT_TUNE BELT=A"
    echo "       BELT_TUNE BELT=B"
    echo "       BELT_COMPARE"
    echo ""
    echo "======================================================================"
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    echo ""
    echo "======================================================================"
    echo " Live Belt Tension Tuner - Installation"
    echo "======================================================================"
    echo ""

    check_klipper
    check_moonraker
    check_gcode_shell_command
    check_accelerometer
    install_dependencies
    clone_or_update
    set_permissions
    install_macros
    install_klipperscreen_panel
    add_moonraker_config

    print_instructions
    print_msg "Installation successful!"
}

main
