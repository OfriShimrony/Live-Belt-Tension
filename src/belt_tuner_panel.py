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

    Two modes:
      - Measure mode: saves up to 5 results, shows average, for final verification.
      - Tune mode:    single large display, results NOT saved, for active tensioning.
                      Shows delta vs the other belt if available.
                      After each result: "Again" or "Save & Exit".
    """

    def __init__(self, screen, title):
        super().__init__(screen, title)

        self.current_belt = 'A'
        self.measurements = {'A': [], 'B': []}
        self.max_measurements = 5
        self.measuring = False
        self.measurement_thread = None
        self.tune_mode = False
        self.last_tune_result = None

        # ── Main container ────────────────────────────────────────────────────
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(5)
        main_box.set_margin_bottom(5)

        # ── Header: belt selection + tune toggle ──────────────────────────────
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_halign(Gtk.Align.CENTER)

        label = Gtk.Label(label="Belt:")
        label.set_name("belt-tuner-label")
        header_box.pack_start(label, False, False, 0)

        self.belt_a_button = self._gtk.Button("belt-a-button", "Belt A", "color1")
        self.belt_a_button.set_size_request(110, 55)
        self.belt_a_button.connect("clicked", self.switch_belt, 'A')
        header_box.pack_start(self.belt_a_button, False, False, 0)

        self.belt_b_button = self._gtk.Button("belt-b-button", "Belt B", "color2")
        self.belt_b_button.set_size_request(110, 55)
        self.belt_b_button.connect("clicked", self.switch_belt, 'B')
        header_box.pack_start(self.belt_b_button, False, False, 0)

        self.tune_button = self._gtk.Button("tune-mode-button", "Tune Mode", "color3")
        self.tune_button.set_size_request(120, 55)
        self.tune_button.connect("clicked", self.toggle_tune_mode)
        header_box.pack_start(self.tune_button, False, False, 0)

        main_box.pack_start(header_box, False, False, 0)

        # ── MEASURE MODE: 5-box grid ──────────────────────────────────────────
        self.measure_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        self.measurement_grid = Gtk.Grid()
        self.measurement_grid.set_column_spacing(10)
        self.measurement_grid.set_row_spacing(5)
        self.measurement_grid.set_halign(Gtk.Align.CENTER)

        self.measurement_boxes = []
        for i in range(5):
            box = self.create_measurement_box(i)
            self.measurement_boxes.append(box)
            self.measurement_grid.attach(box, i, 0, 1, 1)

        self.measure_widget.pack_start(self.measurement_grid, True, True, 0)
        main_box.pack_start(self.measure_widget, True, True, 0)

        # ── TUNE MODE: single large display ───────────────────────────────────
        self.tune_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        tune_frame = Gtk.Frame()
        tune_frame.get_style_context().add_class("tune-mode-frame")
        tune_frame.set_size_request(-1, 140)

        tune_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tune_inner.set_halign(Gtk.Align.CENTER)
        tune_inner.set_valign(Gtk.Align.CENTER)
        tune_inner.set_margin_top(15)
        tune_inner.set_margin_bottom(15)

        self.tune_freq_label = Gtk.Label()
        self.tune_freq_label.set_markup("<span size='xxx-large'>---</span>")
        tune_inner.pack_start(self.tune_freq_label, False, False, 0)

        self.tune_hz_label = Gtk.Label(label="Hz")
        self.tune_hz_label.set_name("belt-tuner-label")
        tune_inner.pack_start(self.tune_hz_label, False, False, 0)

        self.tune_quality_label = Gtk.Label()
        tune_inner.pack_start(self.tune_quality_label, False, False, 0)

        self.tune_delta_label = Gtk.Label()
        tune_inner.pack_start(self.tune_delta_label, False, False, 0)

        tune_frame.add(tune_inner)
        self.tune_widget.pack_start(tune_frame, True, True, 0)
        main_box.pack_start(self.tune_widget, True, True, 0)
        self.tune_widget.hide()

        # ── Shared: status + average + start button ───────────────────────────
        self.status_label = Gtk.Label()
        self.status_label.set_name("belt-tuner-status")
        self.status_label.set_markup("<big>Ready</big>")
        self.status_label.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(self.status_label, False, False, 5)

        self.average_label = Gtk.Label()
        self.average_label.set_name("belt-tuner-average")
        self.average_label.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(self.average_label, False, False, 0)

        self.start_button = self._gtk.Button("start-measurement", "START MEASUREMENT", "color3")
        self.start_button.set_size_request(-1, 60)
        self.start_button.connect("clicked", self.start_measurement)
        main_box.pack_start(self.start_button, False, False, 5)

        # ── MEASURE MODE action buttons ───────────────────────────────────────
        self.measure_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.measure_actions.set_halign(Gtk.Align.CENTER)

        self.compare_button = self._gtk.Button("compare-button", "Compare Belts", "color4")
        self.compare_button.set_size_request(150, 45)
        self.compare_button.connect("clicked", self.show_comparison)
        self.measure_actions.pack_start(self.compare_button, False, False, 0)

        clear_button = self._gtk.Button("clear-button", "Clear All", "color2")
        clear_button.set_size_request(110, 45)
        clear_button.connect("clicked", self.clear_measurements)
        self.measure_actions.pack_start(clear_button, False, False, 0)

        main_box.pack_start(self.measure_actions, False, False, 5)

        # ── TUNE MODE action buttons (hidden until first result) ──────────────
        self.tune_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.tune_actions.set_halign(Gtk.Align.CENTER)

        again_button = self._gtk.Button("tune-again-button", "Again", "color3")
        again_button.set_size_request(120, 45)
        again_button.connect("clicked", self.tune_again)
        self.tune_actions.pack_start(again_button, False, False, 0)

        save_exit_button = self._gtk.Button("tune-save-button", "Save & Exit", "color4")
        save_exit_button.set_size_request(140, 45)
        save_exit_button.connect("clicked", self.tune_save_and_exit)
        self.tune_actions.pack_start(save_exit_button, False, False, 0)

        main_box.pack_start(self.tune_actions, False, False, 5)
        self.tune_actions.hide()

        # ── Info label ────────────────────────────────────────────────────────
        self.info_label = Gtk.Label()
        self.info_label.set_markup("<small>Recommendation: Take 3-5 measurements for accuracy</small>")
        self.info_label.set_halign(Gtk.Align.CENTER)
        self.info_label.set_margin_top(5)
        main_box.pack_start(self.info_label, False, False, 0)

        self.content.add(main_box)

        self.update_belt_selection()
        self.update_measurements_display()

    # ── Measurement box creation ──────────────────────────────────────────────

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

    # ── Belt selection ────────────────────────────────────────────────────────

    def switch_belt(self, widget, belt):
        if self.measuring:
            return
        self.current_belt = belt
        self.update_belt_selection()
        if self.tune_mode:
            self._reset_tune_display()
        else:
            self.update_measurements_display()
            self.update_average_display()

    def update_belt_selection(self):
        if self.current_belt == 'A':
            self.belt_a_button.get_style_context().add_class("button_active")
            self.belt_b_button.get_style_context().remove_class("button_active")
        else:
            self.belt_b_button.get_style_context().add_class("button_active")
            self.belt_a_button.get_style_context().remove_class("button_active")

    # ── Tune mode toggle ──────────────────────────────────────────────────────

    def toggle_tune_mode(self, widget):
        if self.measuring:
            return
        self.tune_mode = not self.tune_mode
        if self.tune_mode:
            self.measure_widget.hide()
            self.measure_actions.hide()
            self.average_label.hide()
            self.info_label.hide()
            self.tune_widget.show()
            self.tune_button.get_style_context().add_class("button_active")
            self._reset_tune_display()
            self.update_status("<big>Tune Mode — Ready</big>")
        else:
            self.tune_widget.hide()
            self.tune_actions.hide()
            self.measure_widget.show()
            self.measure_actions.show()
            self.average_label.show()
            self.info_label.show()
            self.tune_button.get_style_context().remove_class("button_active")
            self.last_tune_result = None
            self.update_status("<big>Ready</big>")
            self.update_measurements_display()
            self.update_average_display()

    def _reset_tune_display(self):
        self.tune_freq_label.set_markup("<span size='xxx-large'>---</span>")
        self.tune_quality_label.set_text("")
        self.tune_delta_label.set_text("")
        self.tune_actions.hide()
        self.last_tune_result = None

    # ── Tune mode results ─────────────────────────────────────────────────────

    def tune_complete(self, result):
        freq = result['frequency']
        q = result['q_factor']
        conf = result['confidence']

        if q > 20:
            color = "#00CC00"
        elif q > 10:
            color = "#FFAA00"
        else:
            color = "#FF4444"

        self.tune_freq_label.set_markup(
            f"<span size='xxx-large' color='{color}'><b>{freq:.1f}</b></span>"
        )
        self.tune_quality_label.set_markup(f"<small>Q={q:.0f}  ({conf})</small>")

        # Delta vs other belt
        other_belt = 'B' if self.current_belt == 'A' else 'A'
        other_meas = self.measurements[other_belt]
        if other_meas:
            other_avg = sum(m['frequency'] for m in other_meas) / len(other_meas)
            delta = freq - other_avg
            abs_delta = abs(delta)
            arrow = "↑ tighten" if delta < 0 else "↓ loosen"
            if abs_delta < 2:
                d_color = "#00CC00"
                d_text = f"Δ vs Belt {other_belt}: {abs_delta:.1f} Hz  ✓ matched"
            elif abs_delta < 5:
                d_color = "#FFAA00"
                d_text = f"Δ vs Belt {other_belt}: {abs_delta:.1f} Hz  {arrow}"
            else:
                d_color = "#FF4444"
                d_text = f"Δ vs Belt {other_belt}: {abs_delta:.1f} Hz  {arrow}"
            self.tune_delta_label.set_markup(f"<span color='{d_color}'>{d_text}</span>")
        else:
            self.tune_delta_label.set_markup(
                f"<small><span color='#888888'>Measure Belt {'B' if self.current_belt == 'A' else 'A'} to see delta</span></small>"
            )

        self.update_status(f"<big><b>{freq:.1f} Hz</b></big>  <small>{conf}</small>")
        self.tune_actions.show()

    def tune_again(self, widget):
        self._reset_tune_display()
        self.start_measurement(widget)

    def tune_save_and_exit(self, widget):
        if self.last_tune_result:
            self.measurements[self.current_belt].append(self.last_tune_result)
        self.toggle_tune_mode(widget)

    # ── Measure mode display ──────────────────────────────────────────────────

    def update_measurements_display(self):
        measurements = self.measurements[self.current_belt]

        for i, event_box in enumerate(self.measurement_boxes):
            box_frame = event_box.get_child()   # EventBox → Frame
            box = box_frame.get_child()          # Frame → Box
            freq_label = box.get_children()[0]
            quality_label = box.get_children()[2]

            box_frame.get_style_context().remove_class("measurement-good")
            box_frame.get_style_context().remove_class("measurement-fair")
            box_frame.get_style_context().remove_class("measurement-poor")
            box_frame.get_style_context().remove_class("measurement-old")

            if i < len(measurements):
                meas = measurements[i]
                freq = meas['frequency']
                q = meas['q_factor']

                freq_label.set_markup(f"<span size='xx-large'>{freq:.1f}</span>")

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

                if i == len(measurements) - 1:
                    box_frame.get_style_context().add_class(style_class)
                else:
                    box_frame.get_style_context().add_class("measurement-old")
            else:
                freq_label.set_markup("<span size='xx-large'>---</span>")
                quality_label.set_text("")

    def update_average_display(self):
        measurements = self.measurements[self.current_belt]

        if len(measurements) == 0:
            self.average_label.set_text("")
            return

        avg_freq = sum(m['frequency'] for m in measurements) / len(measurements)
        high_quality = len([m for m in measurements if m['q_factor'] > 20])

        if high_quality >= len(measurements) * 0.6:
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

    # ── Measurement execution ─────────────────────────────────────────────────

    def start_measurement(self, widget):
        if self.measuring:
            return

        if not self.tune_mode and len(self.measurements[self.current_belt]) >= self.max_measurements:
            self._screen.show_popup_message(
                "Maximum measurements reached. Clear to continue.",
                level=1
            )
            return

        self.measuring = True
        self.start_button.set_sensitive(False)
        self.belt_a_button.set_sensitive(False)
        self.belt_b_button.set_sensitive(False)
        self.tune_button.set_sensitive(False)

        self.measurement_thread = threading.Thread(target=self.measurement_worker)
        self.measurement_thread.daemon = True
        self.measurement_thread.start()

    def measurement_worker(self):
        try:
            for i in [3, 2, 1]:
                GLib.idle_add(self.update_status, f"Pluck in:\n<span size='xx-large'><b>{i}</b></span>")
                time.sleep(0.8)

            GLib.idle_add(self.update_status, "<span size='xx-large' color='#00FF00'><b>PLUCK NOW!</b></span>")

            self._screen._ws.klippy.gcode_script("ACCELEROMETER_MEASURE CHIP=adxl345")
            time.sleep(0.3)
            time.sleep(3.0)
            self._screen._ws.klippy.gcode_script(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=belt_{self.current_belt}_ks")
            time.sleep(0.5)

            GLib.idle_add(self.update_status, "Analyzing...")
            result = self.analyze_measurement()

            if result and 'error' not in result:
                if not self.tune_mode:
                    self.measurements[self.current_belt].append(result)
                else:
                    self.last_tune_result = result
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
        try:
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
                if os.path.exists(analyzer_path):
                    sys.path.insert(0, path)
                    analyzer_found = True
                    break

            if not analyzer_found:
                return {'error': 'belt_analyzer_v3.py not found. Please copy to ~/Live-Belt-Tension/src/'}

            from belt_analyzer_v3 import analyze_pluck_v3 as analyze_pluck_event
            files = glob.glob('/tmp/adxl345-*.csv')
            if not files:
                return {'error': 'No data file found'}

            files.sort(key=os.path.getmtime)
            latest = files[-1]

            if len(files) > 10:
                for old_file in files[:-10]:
                    try:
                        os.remove(old_file)
                    except:
                        pass

            return analyze_pluck_event(latest, self.current_belt, debug=False)

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {'error': str(e)}

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def update_status(self, message):
        self.status_label.set_markup(message)

    def measurement_complete(self, result):
        if self.tune_mode:
            self.tune_complete(result)
        else:
            freq = result['frequency']
            q = result['q_factor']
            conf = result['confidence']
            self.update_status(f"<big><b>{freq:.1f} Hz</b></big>\n<small>Q={q:.0f} ({conf})</small>")
            self.update_measurements_display()
            self.update_average_display()

    def measurement_failed(self, error):
        self.update_status(f"<span color='red'>Error: {error}</span>")
        self._screen.show_popup_message(f"Measurement failed: {error}", level=2)

    def enable_buttons(self):
        self.start_button.set_sensitive(True)
        self.belt_a_button.set_sensitive(True)
        self.belt_b_button.set_sensitive(True)
        self.tune_button.set_sensitive(True)

    def on_measurement_clicked(self, widget, event, index):
        """Tap a measurement box to clear that specific measurement."""
        if self.measuring:
            return
        measurements = self.measurements[self.current_belt]
        if index >= len(measurements):
            return

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
        a_meas = self.measurements['A']
        b_meas = self.measurements['B']

        if len(a_meas) == 0 or len(b_meas) == 0:
            self._screen.show_popup_message(
                "Please measure both belts before comparing.",
                level=1
            )
            return

        avg_a = sum(m['frequency'] for m in a_meas) / len(a_meas)
        avg_b = sum(m['frequency'] for m in b_meas) / len(b_meas)
        delta = abs(avg_a - avg_b)

        a_hq = len([m for m in a_meas if m['q_factor'] > 20])
        b_hq = len([m for m in b_meas if m['q_factor'] > 20])

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

        confidence_warning = ""
        if a_hq < len(a_meas) * 0.5 or b_hq < len(b_meas) * 0.5:
            confidence_warning = "\n<small>(Some measurements had low quality)</small>"

        message = (
            f"<big><b>Belt Comparison</b></big>\n\n"
            f"Belt A: <b>{avg_a:.1f} Hz</b> ({a_hq}/{len(a_meas)} high-quality)\n"
            f"Belt B: <b>{avg_b:.1f} Hz</b> ({b_hq}/{len(b_meas)} high-quality)\n"
            f"Delta: <b>{delta:.1f} Hz</b>\n\n"
            f"<span color='{color}'><big><b>{status}</b></big></span>"
            f"{confidence_warning}"
        )

        self._screen.show_popup_message(message, level=1)
