#!/bin/bash
# Live Belt Tension Tuner - Installation Script
# Based on the Klippain Shake&Tune installation approach

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
KLIPPER_PATH="${HOME}/klipper"
KLIPPER_CONFIG_PATH="${HOME}/printer_data/config"
MOONRAKER_CONFIG="${HOME}/printer_data/config/moonraker.conf"
SYSTEMD_DIR="/etc/systemd/system"
BELT_TUNER_PATH="${HOME}/Live-Belt-Tension"

print_msg() {
    echo -e "${GREEN}[Live Belt Tuner]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

check_klipper() {
    print_msg "Checking Klipper installation..."
    
    if [ ! -d "$KLIPPER_PATH" ]; then
        print_error "Klipper not found at $KLIPPER_PATH"
        print_error "Please install Klipper first"
        exit 1
    fi
    
    print_msg "✓ Klipper found"
}

check_moonraker() {
    print_msg "Checking Moonraker installation..."
    
    if ! systemctl list-units --full -all | grep -q "moonraker.service"; then
        print_error "Moonraker service not found"
        print_error "Please install Moonraker first"
        exit 1
    fi
    
    print_msg "✓ Moonraker found"
}

check_accelerometer() {
    print_msg "Checking for ADXL345 configuration..."
    
    if ! grep -r "adxl345" "$KLIPPER_CONFIG_PATH"/*.cfg 2>/dev/null; then
        print_warning "ADXL345 not found in config files"
        print_warning "Make sure you have an accelerometer configured"
    else
        print_msg "✓ ADXL345 configuration found"
    fi
}

install_dependencies() {
    print_msg "Installing Python dependencies..."
    
    # Check if running in virtual environment (Klipper's env)
    if [ -d "${HOME}/klippy-env" ]; then
        print_msg "Installing to Klipper virtual environment..."
        "${HOME}/klippy-env/bin/pip" install -q numpy scipy 2>/dev/null || {
            print_warning "Could not install to klippy-env, trying system install..."
            sudo apt-get update -qq
            sudo apt-get install -y python3-numpy python3-scipy python3-matplotlib
        }
    else
        print_msg "Installing system packages..."
        sudo apt-get update -qq
        sudo apt-get install -y python3-numpy python3-scipy python3-matplotlib
    fi
    
    print_msg "✓ Dependencies installed"
}

clone_repository() {
    print_msg "Setting up Live Belt Tension Tuner..."
    
    if [ -d "$BELT_TUNER_PATH" ]; then
        print_msg "Repository already exists, updating..."
        cd "$BELT_TUNER_PATH"
        git pull
    else
        print_msg "Cloning repository..."
        git clone https://github.com/OfriShimrony/Live-Belt-Tension.git "$BELT_TUNER_PATH"
    fi
    
    print_msg "✓ Repository ready"
}

make_executable() {
    print_msg "Making scripts executable..."
    
    chmod +x "$BELT_TUNER_PATH/src/"*.py 2>/dev/null || true
    chmod +x "$BELT_TUNER_PATH/tests/"*.py 2>/dev/null || true
    
    print_msg "✓ Scripts are executable"
}

create_symlinks() {
    print_msg "Creating convenient command shortcuts..."
    
    # Create a command to run the live tuner easily
    sudo tee /usr/local/bin/belt-tuner > /dev/null << EOF
#!/bin/bash
cd "$BELT_TUNER_PATH/src"
python3 live_belt_tuner.py "\$@"
EOF
    
    sudo chmod +x /usr/local/bin/belt-tuner
    
    print_msg "✓ You can now run 'belt-tuner' from anywhere!"
}

add_moonraker_config() {
    print_msg "Configuring Moonraker update manager..."
    
    if [ -f "$MOONRAKER_CONFIG" ]; then
        # Check if already configured
        if grep -q "\[update_manager live_belt_tension\]" "$MOONRAKER_CONFIG"; then
            print_msg "✓ Moonraker already configured"
        else
            # Add update manager configuration
            cat >> "$MOONRAKER_CONFIG" << EOF

[update_manager live_belt_tension]
type: git_repo
path: ~/Live-Belt-Tension
origin: https://github.com/OfriShimrony/Live-Belt-Tension.git
primary_branch: main
managed_services: klipper
EOF
            print_msg "✓ Moonraker configuration added"
            print_msg "  Restart Moonraker to enable auto-updates"
        fi
    else
        print_warning "Moonraker config not found at expected location"
        print_warning "You'll need to add update manager configuration manually"
    fi
}

print_instructions() {
    echo ""
    echo "======================================================================"
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "======================================================================"
    echo ""
    echo "You can now use Live Belt Tension Tuner:"
    echo ""
    echo "  1. Run the live tuner:"
    echo "     ${GREEN}belt-tuner${NC}"
    echo ""
    echo "  2. Or run directly:"
    echo "     ${GREEN}cd ~/Live-Belt-Tension/src${NC}"
    echo "     ${GREEN}python3 live_belt_tuner.py${NC}"
    echo ""
    echo "  3. Test your setup:"
    echo "     ${GREEN}cd ~/Live-Belt-Tension/tests${NC}"
    echo "     ${GREEN}python3 adxl_test_v3.py${NC}"
    echo ""
    echo "======================================================================"
    echo "Next steps:"
    echo "  - Run 'belt-tuner' and pluck your belts!"
    echo "  - Check the GitHub repo for updates and documentation"
    echo "  - Report issues: https://github.com/OfriShimrony/Live-Belt-Tension"
    echo "======================================================================"
    echo ""
}

main() {
    echo ""
    echo "======================================================================"
    echo "Live Belt Tension Tuner - Installation"
    echo "======================================================================"
    echo ""
    
    # Run installation steps
    check_klipper
    check_moonraker
    check_accelerometer
    install_dependencies
    clone_repository
    make_executable
    create_symlinks
    add_moonraker_config
    
    # Show instructions
    print_instructions
    
    print_msg "Installation successful!"
}

# Run main installation
main
