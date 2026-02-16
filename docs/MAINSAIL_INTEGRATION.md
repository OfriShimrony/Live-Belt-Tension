# Mainsail Integration for Live Belt Tuner

## Option 1: Add as iFrame Tab (Easiest)

To add the Belt Tuner as a tab in Mainsail:

1. **Open Mainsail** in your browser
2. **Go to Settings** (gear icon)
3. **Navigate to "Interface" → "Custom Tabs"**
4. **Click "Add Tab"**
5. **Fill in:**
   - **Tab Name:** Belt Tuner
   - **Icon:** `mdi-guitar-pick` (or `mdi-tune-vertical`)
   - **URL:** `http://localhost:8585`
   - **Position:** Choose where you want it (e.g., after Tune)
6. **Save**

The Belt Tuner will now appear as a tab in Mainsail!

---

## Option 2: Moonraker Update Manager (For Auto-Updates)

This was already added by the install script, but here's the config for reference:

**File:** `~/printer_data/config/moonraker.conf`

```ini
[update_manager live_belt_tension]
type: git_repo
path: ~/Live-Belt-Tension
origin: https://github.com/OfriShimrony/Live-Belt-Tension.git
primary_branch: main
managed_services: klipper
```

---

## Option 3: Run as System Service (Auto-start)

To make the web server start automatically:

### 1. Create systemd service file:

```bash
sudo nano /etc/systemd/system/belt-tuner-web.service
```

### 2. Add this content:

```ini
[Unit]
Description=Live Belt Tuner Web Server
After=network.target moonraker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Live-Belt-Tension/src
ExecStart=/usr/bin/python3 /home/pi/Live-Belt-Tension/src/belt_tuner_web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable belt-tuner-web.service
sudo systemctl start belt-tuner-web.service
```

### 4. Check status:

```bash
sudo systemctl status belt-tuner-web.service
```

Now the web server will:
- Start automatically on boot
- Restart if it crashes
- Always be available at http://your-printer-ip:8585

---

## Usage in Mainsail

Once integrated:

1. **Click the "Belt Tuner" tab** in Mainsail
2. **Enter your target frequency** (default: 110 Hz)
3. **Click "Start"**
4. **Pluck your belt** and watch the needle move
5. **Adjust tension** to match the target (green zone)
6. **Click "Stop"** when done

The gauge shows:
- **White needle:** Current frequency
- **Green zone:** Target ± 5 Hz tolerance
- **White line in green zone:** Exact target
- **Status:** Shows if you need to tighten or loosen

---

## Troubleshooting

**Tab doesn't load:**
- Make sure the web server is running: `systemctl status belt-tuner-web.service`
- Check the URL is correct: `http://localhost:8585`

**Can't access from other devices:**
- Use your printer's IP instead of localhost
- Example: `http://192.168.1.100:8585`

**Web server not starting:**
- Check logs: `journalctl -u belt-tuner-web.service -f`
- Verify dependencies: `pip3 list | grep aiohttp`
