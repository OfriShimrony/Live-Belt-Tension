#!/usr/bin/env python3
"""
Live Belt Tuner - Web Server
-----------------------------
Provides a web-based UI for belt tension monitoring.
Access via browser at http://your-printer-ip:8585

Usage:
    python3 belt_tuner_web.py
    
Then open: http://your-printer-ip:8585
"""

import asyncio
import json
import time
import os
import numpy as np
from scipy import signal
from aiohttp import web
import aiohttp
import threading
import queue

# Configuration
MOONRAKER_URL = "http://localhost:7125"
WEB_PORT = 8585
MEASUREMENT_DURATION = 2.0

class BeltTunerWeb:
    def __init__(self):
        self.running = False
        self.latest_data = {
            'frequency': 0,
            'magnitude': 0,
            'status': 'idle',
            'timestamp': 0
        }
        self.data_lock = threading.Lock()
        self.measurement_thread = None
        
    async def moonraker_request(self, endpoint, params=None):
        """Make request to Moonraker"""
        try:
            url = f"{MOONRAKER_URL}{endpoint}"
            async with aiohttp.ClientSession() as session:
                if params:
                    async with session.post(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            return await resp.json()
                else:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            return await resp.json()
        except Exception as e:
            print(f"Moonraker error: {e}")
        return None
    
    def find_latest_csv(self):
        """Find most recent CSV file"""
        data_dir = "/tmp"
        try:
            files = []
            for filename in os.listdir(data_dir):
                if filename.startswith("adxl345-") and filename.endswith(".csv"):
                    filepath = os.path.join(data_dir, filename)
                    files.append((filepath, os.path.getmtime(filepath)))
            
            if files:
                files.sort(key=lambda x: x[1], reverse=True)
                return files[0][0]
        except:
            pass
        return None
    
    def analyze_data(self, filepath):
        """Perform FFT analysis on data file"""
        try:
            data = np.genfromtxt(filepath, delimiter=',', skip_header=0)
            if len(data) < 100:
                return None
            
            accel_x = data[:, 1]
            times = data[:, 0]
            dt = np.mean(np.diff(times))
            sample_rate = 1.0 / dt
            
            # FFT processing
            signal_data = accel_x - np.mean(accel_x)
            window = np.hanning(len(signal_data))
            signal_windowed = signal_data * window
            
            fft_result = np.fft.rfft(signal_windowed)
            fft_freq = np.fft.rfftfreq(len(signal_windowed), 1.0/sample_rate)
            fft_magnitude = np.abs(fft_result)
            
            # Belt frequency range
            belt_range = (fft_freq >= 50) & (fft_freq <= 200)
            belt_freq = fft_freq[belt_range]
            belt_mag = fft_magnitude[belt_range]
            
            if len(belt_mag) > 0:
                peak_indices = signal.find_peaks(belt_mag, height=np.max(belt_mag)*0.3)[0]
                if len(peak_indices) > 0:
                    sorted_peaks = sorted(peak_indices, key=lambda i: belt_mag[i], reverse=True)
                    peak_freq = belt_freq[sorted_peaks[0]]
                    peak_magnitude = belt_mag[sorted_peaks[0]]
                    
                    return {
                        'frequency': float(peak_freq),
                        'magnitude': float(peak_magnitude),
                        'sample_rate': float(sample_rate),
                        'samples': len(data)
                    }
            
            return None
        except Exception as e:
            print(f"Analysis error: {e}")
            return None
    
    def measurement_worker(self):
        """Background thread for measurements"""
        import requests
        count = 0
        
        while self.running:
            try:
                # Start measurement
                url = f"{MOONRAKER_URL}/printer/gcode/script"
                requests.post(url, params={"script": "ACCELEROMETER_MEASURE CHIP=adxl345"}, timeout=10)
                
                time.sleep(MEASUREMENT_DURATION)
                
                # Stop measurement
                name = f"web_{count}"
                requests.post(url, params={"script": f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME={name}"}, timeout=10)
                count += 1
                
                time.sleep(0.3)
                
                # Analyze
                csv_file = self.find_latest_csv()
                if csv_file:
                    result = self.analyze_data(csv_file)
                    if result:
                        with self.data_lock:
                            self.latest_data = {
                                'frequency': result['frequency'],
                                'magnitude': result['magnitude'],
                                'status': 'measuring',
                                'timestamp': time.time()
                            }
                
            except Exception as e:
                print(f"Measurement error: {e}")
                time.sleep(1)
    
    async def handle_index(self, request):
        """Serve main HTML page"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Live Belt Tuner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: white;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        .frequency-display {
            text-align: center;
            font-size: 4em;
            font-weight: bold;
            margin: 20px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .gauge-container {
            position: relative;
            height: 200px;
            margin: 30px 0;
        }
        .gauge {
            width: 100%;
            height: 100%;
        }
        .status {
            text-align: center;
            font-size: 1.5em;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .status.idle { background: rgba(128, 128, 128, 0.3); }
        .status.measuring { background: rgba(76, 175, 80, 0.3); }
        .status.good { background: rgba(76, 175, 80, 0.5); }
        .status.loose { background: rgba(255, 152, 0, 0.5); }
        .status.tight { background: rgba(244, 67, 54, 0.5); }
        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 20px;
        }
        button {
            padding: 15px 30px;
            font-size: 1.2em;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            transition: all 0.3s;
        }
        button:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        button:active {
            transform: translateY(0);
        }
        button.active {
            background: #4CAF50;
        }
        .info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        .info-item {
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .info-item label {
            display: block;
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        .info-item value {
            font-size: 1.5em;
            font-weight: bold;
        }
        .target-input {
            background: rgba(0, 0, 0, 0.2);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        .target-input label {
            display: block;
            font-size: 1.1em;
            margin-bottom: 10px;
        }
        .target-input input {
            width: 100%;
            padding: 10px;
            font-size: 1.5em;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            text-align: center;
        }
        .target-input input:focus {
            outline: none;
            border-color: rgba(255, 255, 255, 0.6);
        }
        .tolerance-info {
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎸 Live Belt Tuner</h1>
            <p>Real-time belt tension monitoring</p>
        </div>
        
        <div class="card">
            <div class="frequency-display" id="frequency">-- Hz</div>
            <div class="gauge-container">
                <canvas id="gauge" class="gauge"></canvas>
            </div>
            <div class="status idle" id="status">Idle - Click Start to begin</div>
        </div>
        
        <div class="card">
            <div class="target-input">
                <label>Target Frequency</label>
                <input type="number" id="targetFreq" value="110" min="50" max="200" step="0.1" onchange="updateTarget()">
                <div class="tolerance-info">± 5 Hz tolerance</div>
            </div>
            
            <div class="controls">
                <button id="startBtn" onclick="startMeasurement()">▶ Start</button>
                <button id="stopBtn" onclick="stopMeasurement()" style="display:none;">⏸ Stop</button>
            </div>
            
            <div class="info">
                <div class="info-item">
                    <label>Target</label>
                    <value id="targetDisplay">110 Hz</value>
                </div>
                <div class="info-item">
                    <label>Deviation</label>
                    <value id="deviation">-- Hz</value>
                </div>
            </div>
        </div>
    </div>

    <script>
        let measuring = false;
        let updateInterval = null;
        let targetFreq = 110;
        let tolerance = 5;
        const canvas = document.getElementById('gauge');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        
        function updateTarget() {
            targetFreq = parseFloat(document.getElementById('targetFreq').value);
            document.getElementById('targetDisplay').textContent = targetFreq.toFixed(1) + ' Hz';
            drawGauge(parseFloat(document.getElementById('frequency').textContent) || 0);
        }
        
        function drawGauge(frequency) {
            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height - 20;
            const radius = Math.min(width, height) - 40;
            
            ctx.clearRect(0, 0, width, height);
            
            // Background arc
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.lineWidth = 30;
            ctx.stroke();
            
            // Target zone (target ± tolerance) - green
            const minTarget = targetFreq - tolerance;
            const maxTarget = targetFreq + tolerance;
            const minAngle = Math.PI + (Math.PI * (minTarget - 50) / 150);
            const maxAngle = Math.PI + (Math.PI * (maxTarget - 50) / 150);
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, minAngle, maxAngle);
            ctx.strokeStyle = 'rgba(76, 175, 80, 0.5)';
            ctx.lineWidth = 30;
            ctx.stroke();
            
            // Target line (exact target)
            const targetAngle = Math.PI + (Math.PI * (targetFreq - 50) / 150);
            const targetLineStart = radius - 35;
            const targetLineEnd = radius - 5;
            ctx.beginPath();
            ctx.moveTo(
                centerX + targetLineStart * Math.cos(targetAngle),
                centerY + targetLineStart * Math.sin(targetAngle)
            );
            ctx.lineTo(
                centerX + targetLineEnd * Math.cos(targetAngle),
                centerY + targetLineEnd * Math.sin(targetAngle)
            );
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // Current value needle
            if (frequency > 0) {
                const angle = Math.PI + (Math.PI * (frequency - 50) / 150);
                const needleLength = radius - 15;
                
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(
                    centerX + needleLength * Math.cos(angle),
                    centerY + needleLength * Math.sin(angle)
                );
                ctx.strokeStyle = 'white';
                ctx.lineWidth = 4;
                ctx.stroke();
                
                // Needle dot
                ctx.beginPath();
                ctx.arc(centerX, centerY, 8, 0, 2 * Math.PI);
                ctx.fillStyle = 'white';
                ctx.fill();
            }
            
            // Scale markers
            ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
            ctx.font = '14px Arial';
            ctx.textAlign = 'center';
            [50, 75, 100, 125, 150, 175, 200].forEach(freq => {
                const angle = Math.PI + (Math.PI * (freq - 50) / 150);
                const x = centerX + (radius + 20) * Math.cos(angle);
                const y = centerY + (radius + 20) * Math.sin(angle);
                ctx.fillText(freq, x, y + 5);
            });
        }
        
        async function updateData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.frequency > 0) {
                    document.getElementById('frequency').textContent = data.frequency.toFixed(1) + ' Hz';
                    drawGauge(data.frequency);
                    
                    // Calculate deviation
                    const deviation = data.frequency - targetFreq;
                    const deviationEl = document.getElementById('deviation');
                    if (deviation > 0) {
                        deviationEl.textContent = '+' + deviation.toFixed(1) + ' Hz';
                    } else {
                        deviationEl.textContent = deviation.toFixed(1) + ' Hz';
                    }
                    
                    // Update status
                    const statusEl = document.getElementById('status');
                    
                    if (Math.abs(deviation) <= tolerance) {
                        statusEl.className = 'status good';
                        statusEl.textContent = '✓ ON TARGET';
                    } else if (deviation < -tolerance) {
                        statusEl.className = 'status loose';
                        statusEl.textContent = '⬇️ TOO LOOSE - Tighten belt (' + Math.abs(deviation).toFixed(1) + ' Hz low)';
                    } else {
                        statusEl.className = 'status tight';
                        statusEl.textContent = '⬆️ TOO TIGHT - Loosen belt (' + deviation.toFixed(1) + ' Hz high)';
                    }
                }
            } catch (error) {
                console.error('Update error:', error);
            }
        }
        
        async function startMeasurement() {
            const response = await fetch('/api/start', { method: 'POST' });
            if (response.ok) {
                measuring = true;
                document.getElementById('startBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'block';
                document.getElementById('status').textContent = 'Starting measurements...';
                document.getElementById('status').className = 'status measuring';
                
                updateInterval = setInterval(updateData, 1000);
            }
        }
        
        async function stopMeasurement() {
            const response = await fetch('/api/stop', { method: 'POST' });
            if (response.ok) {
                measuring = false;
                document.getElementById('startBtn').style.display = 'block';
                document.getElementById('stopBtn').style.display = 'none';
                document.getElementById('status').textContent = 'Stopped';
                document.getElementById('status').className = 'status idle';
                
                if (updateInterval) {
                    clearInterval(updateInterval);
                }
            }
        }
        
        // Initial gauge draw
        drawGauge(0);
        
        // Handle window resize
        window.addEventListener('resize', () => {
            canvas.width = canvas.offsetWidth;
            canvas.height = canvas.offsetHeight;
            drawGauge(0);
        });
    </script>
</body>
</html>
"""
        return web.Response(text=html, content_type='text/html')
    
    async def handle_status(self, request):
        """API endpoint for current status"""
        with self.data_lock:
            return web.json_response(self.latest_data)
    
    async def handle_start(self, request):
        """Start measurements"""
        if not self.running:
            self.running = True
            self.measurement_thread = threading.Thread(target=self.measurement_worker, daemon=True)
            self.measurement_thread.start()
        return web.json_response({'status': 'started'})
    
    async def handle_stop(self, request):
        """Stop measurements"""
        self.running = False
        if self.measurement_thread:
            self.measurement_thread.join(timeout=3)
        
        with self.data_lock:
            self.latest_data['status'] = 'idle'
        
        return web.json_response({'status': 'stopped'})
    
    async def start_server(self):
        """Start web server"""
        app = web.Application()
        app.router.add_get('/', self.handle_index)
        app.router.add_get('/api/status', self.handle_status)
        app.router.add_post('/api/start', self.handle_start)
        app.router.add_post('/api/stop', self.handle_stop)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
        await site.start()
        
        print("="*60)
        print("Live Belt Tuner Web Server")
        print("="*60)
        print(f"\n✓ Server running on port {WEB_PORT}")
        print(f"\nAccess the interface at:")
        print(f"  http://localhost:{WEB_PORT}")
        print(f"  or")
        print(f"  http://YOUR_PRINTER_IP:{WEB_PORT}")
        print(f"\nPress Ctrl+C to stop")
        print("="*60)
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            print("\n\nStopping server...")
            self.running = False

def main():
    tuner = BeltTunerWeb()
    asyncio.run(tuner.start_server())

if __name__ == "__main__":
    main()
