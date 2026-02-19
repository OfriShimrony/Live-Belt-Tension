import gi
import logging
import os
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.BeltTuner")

class Panel(ScreenPanel):
    """
    Belt Tension Tuner Panel for KlipperScreen
    
    Touch-friendly interface for measuring belt tension with visual feedback.
    """
    
    def __init__(self, screen, title):
        super().__init__(screen, title)
        
        self.current_belt = 'A'
        self.measurements = {'A': [], 'B': []}
        self.max_measurements = 5
        self.measuring = False
        self.measurement_thread = None
        
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(5)
        main_box.set_margin_bottom(5)
        
        # Header - Belt selection
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        header_box.set_halign(Gtk.Align.CENTER)
        
        label = Gtk.Label(label="Select Belt:")
        label.set_name("belt-tuner-label")
        header_box.pack_start(label, False, False, 0)
        
        # Belt A button
        self.belt_a_button = self._gtk.Button("belt-a-button", "Belt A", "color1")
        self.belt_a_button.set_size_request(120, 60)
        self.belt_a_button.connect("clicked", self.switch_belt, 'A')
        header_box.pack_start(self.belt_a_button, False, False, 0)
        
        # Belt B button
        self.belt_b_button = self._gtk.Button("belt-b-button", "Belt B", "color2")
        self.belt_b_button.set_size_request(120, 60)
        self.belt_b_button.connect("clicked", self.switch_belt, 'B')
        header_box.pack_start(self.belt_b_button, False, False, 0)
        
        main_box.pack_start(header_box, False, False, 0)
        
        # Measurement boxes container
        self.measurement_grid = Gtk.Grid()
        self.measurement_grid.set_column_spacing(10)
        self.measurement_grid.set_row_spacing(5)
        self.measurement_grid.set_halign(Gtk.Align.CENTER)
        
        # Create 5 measurement boxes
        self.measurement_boxes = []
        for i in range(5):
            box = self.create_measurement_box(i)
            self.measurement_boxes.append(box)
            self.measurement_grid.attach(box, i, 0, 1, 1)
        
        main_box.pack_start(self.measurement_grid, True, True, 0)
        
        # Status/countdown label
        self.status_label = Gtk.Label()
        self.status_label.set_name("belt-tuner-status")
        self.status_label.set_markup("<big>Ready</big>")
        self.status_label.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(self.status_label, False, False, 5)
        
        # Average display
        self.average_label = Gtk.Label()
        self.average_label.set_name("belt-tuner-average")
        self.average_label.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(self.average_label, False, False, 0)
        
        # Start button
        self.start_button = self._gtk.Button("start-measurement", "START MEASUREMENT", "color3")
        self.start_button.set_size_request(-1, 60)
        self.start_button.connect("clicked", self.start_measurement)
        main_box.pack_start(self.start_button, False, False, 5)
        
        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_box.set_halign(Gtk.Align.CENTER)
        
        self.compare_button = self._gtk.Button("compare-button", "Compare Belts", "color4")
        self.compare_button.set_size_request(150, 45)
        self.compare_button.connect("clicked", self.show_comparison)
        action_box.pack_start(self.compare_button, False, False, 0)
        
        clear_button = self._gtk.Button("clear-button", "Clear All", "color2")
        clear_button.set_size_request(110, 45)
        clear_button.connect("clicked", self.clear_measurements)
        action_box.pack_start(clear_button, False, False, 0)
        
        main_box.pack_start(action_box, False, False, 5)
        
        # Info label
        info_label = Gtk.Label()
        info_label.set_markup("<small>Recommendation: Take 3-5 measurements for accuracy</small>")
        info_label.set_halign(Gtk.Align.CENTER)
        info_label.set_margin_top(5)
        main_box.pack_start(info_label, False, False, 0)
        
        self.content.add(main_box)
        
        # Update UI
        self.update_belt_selection()
        self.update_measurements_display()
    
    def create_measurement_box(self, index):
        """Create a single measurement display box, tappable to clear that measurement."""
        event_box = Gtk.EventBox()
        event_box.connect("button-press-event", self.on_measurement_clicked, index)

        frame = Gtk.Frame()
        frame.set_size_request(100, 100)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        freq_label = Gtk.Label()
        freq_label.set_name(f"measurement-freq-{index}")
        freq_label.set_markup("<span size='xx-large'>---</span>")
        box.pack_start(freq_label, False, False, 0)

        unit_label = Gtk.Label(label="Hz")
        unit_label.set_name(f"measurement-unit-{index}")
        box.pack_start(unit_label, False, False, 0)

        quality_label = Gtk.Label()
        quality_label.set_name(f"measurement-quality-{index}")
        box.pack_start(quality_label, False, False, 0)

        frame.add(box)
        event_box.add(frame)
        return event_box
    
    def switch_belt(self, widget, belt):
        """Switch between Belt A and Belt B"""
        if self.measuring:
            return
        
        self.current_belt = belt
        self.update_belt_selection()
        self.update_measurements_display()
        self.update_average_display()
    
    def update_belt_selection(self):
        """Update button styles to show selection"""
        if self.current_belt == 'A':
            self.belt_a_button.get_style_context().add_class("button_active")
            self.belt_b_button.get_style_context().remove_class("button_active")
        else:
            self.belt_b_button.get_style_context().add_class("button_active")
            self.belt_a_button.get_style_context().remove_class("button_active")
    
    def update_measurements_display(self):
        """Update the measurement boxes with current data"""
        measurements = self.measurements[self.current_belt]
        
        for i, event_box in enumerate(self.measurement_boxes):
            box_frame = event_box.get_child()   # EventBox → Frame
            box = box_frame.get_child()          # Frame → Box
            freq_label = box.get_children()[0]
            quality_label = box.get_children()[2]

            # Clear previous styling
            box_frame.get_style_context().remove_class("measurement-good")
            box_frame.get_style_context().remove_class("measurement-fair")
            box_frame.get_style_context().remove_class("measurement-poor")
            box_frame.get_style_context().remove_class("measurement-old")
            
            if i < len(measurements):
                meas = measurements[i]
                freq = meas['frequency']
                q = meas['q_factor']
                
                # Update frequency
                freq_label.set_markup(f"<span size='xx-large'>{freq:.1f}</span>")
                
                # Update quality indicator
                if q > 50:
                    quality_label.set_text("✓✓")
                    style_class = "measurement-good"
                elif q > 20:
                    quality_label.set_text("✓")
                    style_class = "measurement-good"
                elif q > 10:
                    quality_label.set_text("~")
                    style_class = "measurement-fair"
                else:
                    quality_label.set_text("✗")
                    style_class = "measurement-poor"
                
                # Newest measurement is bright, older ones fade
                if i == len(measurements) - 1:
                    box_frame.get_style_context().add_class(style_class)
                else:
                    box_frame.get_style_context().add_class("measurement-old")

            else:
                freq_label.set_markup("<span size='xx-large'>---</span>")
                quality_label.set_text("")
    
    def update_average_display(self):
        """Update the average frequency display"""
        measurements = self.measurements[self.current_belt]
        
        if len(measurements) == 0:
            self.average_label.set_text("")
            return
        
        # Calculate average from all measurements
        avg_freq = sum(m['frequency'] for m in measurements) / len(measurements)
        
        # Count high-quality measurements (Q > 20)
        high_quality = len([m for m in measurements if m['q_factor'] > 20])
        
        # Determine confidence level
        if high_quality >= len(measurements) * 0.6:  # 60%+ high quality
            confidence_text = "HIGH"
            color = "green"
        elif high_quality > 0:
            confidence_text = "MEDIUM"
            color = "orange"
        else:
            confidence_text = "LOW"
            color = "orange"
        
        self.average_label.set_markup(
            f"<big>Average: <b>{avg_freq:.1f} Hz</b></big> "
            f"<small><span color='{color}'>{confidence_text} confidence</span> "
            f"({high_quality}/{len(measurements)} high-quality)</small>"
        )
    
    def start_measurement(self, widget):
        """Start a new measurement"""
        if self.measuring:
            return
        
        if len(self.measurements[self.current_belt]) >= self.max_measurements:
            self._screen.show_popup_message(
                "Maximum measurements reached. Clear to continue.",
                level=1
            )
            return
        
        self.measuring = True
        self.start_button.set_sensitive(False)
        self.belt_a_button.set_sensitive(False)
        self.belt_b_button.set_sensitive(False)
        
        # Start measurement in thread
        self.measurement_thread = threading.Thread(target=self.measurement_worker)
        self.measurement_thread.daemon = True
        self.measurement_thread.start()
    
    def measurement_worker(self):
        """Worker thread for measurement (countdown and capture)"""
        try:
            # Countdown
            for i in [3, 2, 1]:
                GLib.idle_add(self.update_status, f"Pluck in:\n<span size='xx-large'><b>{i}</b></span>")
                time.sleep(0.8)
            
            # Pluck now
            GLib.idle_add(self.update_status, "<span size='xx-large' color='#00FF00'><b>PLUCK NOW!</b></span>")
            
            # Start ADXL measurement
            self._screen._ws.klippy.gcode_script("ACCELEROMETER_MEASURE CHIP=adxl345")
            time.sleep(0.3)
            
            # Record for 3 seconds
            time.sleep(3.0)
            
            # Stop measurement
            self._screen._ws.klippy.gcode_script(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=belt_{self.current_belt}_ks")
            time.sleep(0.5)
            
            # Analyze
            GLib.idle_add(self.update_status, "Analyzing...")
            result = self.analyze_measurement()
            
            if result and 'error' not in result:
                # Add to measurements
                self.measurements[self.current_belt].append(result)
                GLib.idle_add(self.measurement_complete, result)
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'Analysis failed'
                GLib.idle_add(self.measurement_failed, error_msg)
        
        except Exception as e:
            logger.error(f"Measurement error: {e}")
            GLib.idle_add(self.measurement_failed, str(e))
        finally:
            self.measuring = False
            GLib.idle_add(self.enable_buttons)
    
    def analyze_measurement(self):
        """Run belt analysis on the latest CSV file"""
        try:
            # Import analyzer from project directory
            import sys
            import glob
            
            project_paths = [
                '/home/pi/Live-Belt-Tension/src',
                '/home/mks/Live-Belt-Tension/src',
                '/home/biqu/Live-Belt-Tension/src',
                os.path.join(os.path.expanduser('~'), 'Live-Belt-Tension', 'src'),
            ]
            
            analyzer_found = False
            for path in project_paths:
                analyzer_path = os.path.join(path, 'belt_analyzer_v3.py')
                logger.info(f"Checking for analyzer at: {analyzer_path}")
                if os.path.exists(analyzer_path):
                    logger.info(f"Found analyzer at: {analyzer_path}")
                    sys.path.insert(0, path)
                    analyzer_found = True
                    break
            
            if not analyzer_found:
                logger.error(f"belt_analyzer_v3.py not found in any of: {project_paths}")
                return {'error': 'belt_analyzer_v3.py not found. Please copy to ~/Live-Belt-Tension/src/'}
            
            from belt_analyzer_v3 import analyze_pluck_v3 as analyze_pluck_event
            files = glob.glob('/tmp/adxl345-*.csv')
            if not files:
                return {'error': 'No data file found'}
            
            # Sort by modification time
            files.sort(key=os.path.getmtime)
            latest = files[-1]
            
            # Cleanup old CSV files - keep last 10
            if len(files) > 10:
                for old_file in files[:-10]:
                    try:
                        os.remove(old_file)
                        logger.info(f"Cleaned up old file: {old_file}")
                    except:
                        pass
            
            # Analyze
            result = analyze_pluck_event(latest, self.current_belt, debug=False)
            return result
        
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {'error': str(e)}
    
    def update_status(self, message):
        """Update status label"""
        self.status_label.set_markup(message)
    
    def measurement_complete(self, result):
        """Called when measurement completes successfully"""
        freq = result['frequency']
        q = result['q_factor']
        conf = result['confidence']
        
        self.update_status(f"<big><b>{freq:.1f} Hz</b></big>\n<small>Q={q:.0f} ({conf})</small>")
        self.update_measurements_display()
        self.update_average_display()
    
    def measurement_failed(self, error):
        """Called when measurement fails"""
        self.update_status(f"<span color='red'>Error: {error}</span>")
        self._screen.show_popup_message(f"Measurement failed: {error}", level=2)
    
    def enable_buttons(self):
        """Re-enable buttons after measurement"""
        self.start_button.set_sensitive(True)
        self.belt_a_button.set_sensitive(True)
        self.belt_b_button.set_sensitive(True)
    
    def on_measurement_clicked(self, widget, event, index):
        """Tap on a measurement box — offer to clear that specific measurement."""
        if self.measuring:
            return
        measurements = self.measurements[self.current_belt]
        if index >= len(measurements):
            return  # Empty slot, nothing to do

        meas = measurements[index]
        freq = meas['frequency']
        q = meas['q_factor']

        dialog = Gtk.MessageDialog(
            transient_for=self._screen,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Measurement #{index + 1}: {freq:.1f} Hz  (Q={q:.0f})",
        )
        dialog.format_secondary_text("Remove this measurement?")
        dialog.add_button("Clear", Gtk.ResponseType.YES)
        dialog.add_button("Close", Gtk.ResponseType.CANCEL)

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self.measurements[self.current_belt].pop(index)
            self.update_measurements_display()
            self.update_average_display()

    def clear_measurements(self, widget):
        """Clear all measurements for current belt."""
        self.measurements[self.current_belt] = []
        self.update_measurements_display()
        self.update_average_display()
        self.update_status("<big>Ready</big>")
    
    def show_comparison(self, widget):
        """Show comparison between Belt A and Belt B"""
        a_meas = self.measurements['A']
        b_meas = self.measurements['B']
        
        if len(a_meas) == 0 or len(b_meas) == 0:
            self._screen.show_popup_message(
                "Please measure both belts before comparing.",
                level=1
            )
            return
        
        # Calculate averages from all measurements
        avg_a = sum(m['frequency'] for m in a_meas) / len(a_meas)
        avg_b = sum(m['frequency'] for m in b_meas) / len(b_meas)
        delta = abs(avg_a - avg_b)
        
        # Count high-quality measurements
        a_high_quality = len([m for m in a_meas if m['q_factor'] > 20])
        b_high_quality = len([m for m in b_meas if m['q_factor'] > 20])
        
        # Determine status
        if delta < 2:
            status = "✓ EXCELLENT"
            color = "green"
        elif delta < 5:
            status = "✓ GOOD"
            color = "blue"
        elif delta < 10:
            status = "⚠ FAIR"
            color = "orange"
        else:
            status = "✗ POOR"
            color = "red"
        
        # Build confidence warning if needed
        confidence_warning = ""
        if a_high_quality < len(a_meas) * 0.5 or b_high_quality < len(b_meas) * 0.5:
            confidence_warning = "\n<small>(Some measurements had low quality)</small>"
        
        message = (
            f"<big><b>Belt Comparison</b></big>\n\n"
            f"Belt A: <b>{avg_a:.1f} Hz</b> ({a_high_quality}/{len(a_meas)} high-quality)\n"
            f"Belt B: <b>{avg_b:.1f} Hz</b> ({b_high_quality}/{len(b_meas)} high-quality)\n"
            f"Delta: <b>{delta:.1f} Hz</b>\n\n"
            f"<span color='{color}'><big><b>{status}</b></big></span>"
            f"{confidence_warning}"
        )
        
        self._screen.show_popup_message(message, level=1)
