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
MOONRAKER_PATH="${HOME}/moonraker"
MOONRAKER_CONFIG="${KLIPPER_CONFIG_PATH}/moonraker.conf"
MAINSAIL_PATH="${HOME}/mainsail"
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

    # Moonraker virtualenv
    if [ -f "${HOME}/moonraker-env/bin/pip" ]; then
        print_msg "  Installing into moonraker-env..."
        "${HOME}/moonraker-env/bin/pip" install -q numpy scipy || \
            print_warning "  moonraker-env install failed, continuing..."
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

# ── 6. Moonraker component ────────────────────────────────────────────────────

install_moonraker_component() {
    print_msg "Installing Moonraker belt_tuner component..."

    local components_dir="${MOONRAKER_PATH}/moonraker/components"
    if [ ! -d "$components_dir" ]; then
        print_warning "  Moonraker components dir not found at $components_dir — skipping"
        return
    fi

    if [ ! -f "${BELT_TUNER_PATH}/src/belt_tuner_moonraker.py" ]; then
        print_warning "  belt_tuner_moonraker.py not found in repo — skipping component install"
        return
    fi

    cp "${BELT_TUNER_PATH}/src/belt_tuner_moonraker.py" "${components_dir}/belt_tuner.py"
    print_msg "  Component installed to $components_dir/belt_tuner.py"

    # Add [belt_tuner] section to moonraker.conf if missing
    if [ ! -f "$MOONRAKER_CONFIG" ]; then
        print_warning "  moonraker.conf not found — skipping [belt_tuner] section"
        return
    fi

    if grep -q "^\[belt_tuner\]" "$MOONRAKER_CONFIG"; then
        print_msg "  [belt_tuner] already present in moonraker.conf"
    else
        echo -e "\n[belt_tuner]" >> "$MOONRAKER_CONFIG"
        print_msg "  [belt_tuner] added to moonraker.conf"
    fi
}

# ── 7. Mainsail web panel ─────────────────────────────────────────────────────

install_mainsail_panel() {
    print_msg "Installing Mainsail web panel..."

    if [ ! -d "$MAINSAIL_PATH" ]; then
        print_warning "  Mainsail not found at $MAINSAIL_PATH — skipping web panel install"
        return
    fi

    if [ ! -f "${BELT_TUNER_PATH}/src/belt_tuner_web.html" ]; then
        print_warning "  belt_tuner_web.html not found in repo — skipping web panel install"
        return
    fi

    cp "${BELT_TUNER_PATH}/src/belt_tuner_web.html" "${MAINSAIL_PATH}/belt_tuner.html"
    print_msg "  Web panel installed to $MAINSAIL_PATH/belt_tuner.html"
    print_msg "  Access at: http://$(hostname -I | awk '{print $1}')/belt_tuner.html"
    print_msg "  Tip: add it to Mainsail via Settings → Webcams → URL: /belt_tuner.html"
}

# ── 8. Moonraker update manager ───────────────────────────────────────────────

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

# ── 9. Set permissions ────────────────────────────────────────────────────────

set_permissions() {
    print_msg "Setting permissions..."
    chmod +x "${BELT_TUNER_PATH}/src/"*.py 2>/dev/null || true
    print_msg "  Done"
}

# ── 10. Summary ───────────────────────────────────────────────────────────────

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
    echo "  2. Restart services:"
    echo "       sudo systemctl restart klipper"
    echo "       sudo systemctl restart moonraker"
    echo "       sudo systemctl restart KlipperScreen   # if installed"
    echo ""
    echo "  3. Mainsail web panel:"
    echo "       Open: http://$(hostname -I | awk '{print $1}')/belt_tuner.html"
    echo "       Or embed via Mainsail → Settings → Webcams → Add webcam"
    echo "         URL: /belt_tuner.html"
    echo ""
    echo "  4. KlipperScreen panel — add to KlipperScreen config:"
    echo "       [menu __main belt_tuner]"
    echo "       name: Belt Tuner"
    echo "       panel: belt_tuner_panel"
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
    install_moonraker_component
    install_mainsail_panel
    add_moonraker_config

    print_instructions
    print_msg "Installation successful!"
}

main
