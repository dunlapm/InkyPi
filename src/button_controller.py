import logging
import queue
import threading
from datetime import timedelta


logger = logging.getLogger(__name__)

DEFAULT_BUTTONS = {
    "A": {"pin": 5, "action": "previous"},
    "B": {"pin": 6, "action": "next"},
    "C": {"pin": 16, "action": "refresh"},
    "D": {"pin": 24, "action": "status"},
}


class ButtonController:
    """Monitors the Inky Impression buttons and serializes their actions."""

    def __init__(self, action_handler, buttons=None):
        self.action_handler = action_handler
        self.buttons = buttons or DEFAULT_BUTTONS
        self.running = False
        self.event_thread = None
        self.action_thread = None
        self.line_request = None
        self.action_queue = queue.Queue(maxsize=1)
        self.action_lock = threading.Lock()
        self.action_pending = False

    def start(self):
        if self.running:
            return
        try:
            self.line_request, self.offset_actions = self._request_lines()
        except (ImportError, OSError, RuntimeError) as e:
            logger.warning("Physical buttons are unavailable: %s", e)
            return

        self.running = True
        self.event_thread = threading.Thread(
            target=self._event_loop, name="button-events", daemon=True
        )
        self.action_thread = threading.Thread(
            target=self._action_loop, name="button-actions", daemon=True
        )
        self.event_thread.start()
        self.action_thread.start()
        logger.info(
            "Physical button controls started: %s",
            ", ".join(
                f"{label}={config['action']}"
                for label, config in self.buttons.items()
            ),
        )

    def stop(self):
        self.running = False
        if self.event_thread:
            self.event_thread.join(timeout=2)
        if self.action_thread:
            self.action_thread.join(timeout=2)
        if self.line_request:
            self.line_request.release()
            self.line_request = None

    def submit_action(self, action):
        with self.action_lock:
            if self.action_pending:
                logger.info(
                    "Ignoring button action '%s' while the display is busy.", action
                )
                return False
            self.action_pending = True
            self.action_queue.put_nowait(action)
            return True

    def _request_lines(self):
        import gpiod
        import gpiodevice
        from gpiod.line import Bias, Direction, Edge

        chip = gpiodevice.find_chip_by_platform()
        offsets = {
            chip.line_offset_from_id(config["pin"]): config["action"]
            for config in self.buttons.values()
        }
        settings = gpiod.LineSettings(
            direction=Direction.INPUT,
            bias=Bias.PULL_UP,
            edge_detection=Edge.FALLING,
            debounce_period=timedelta(milliseconds=150),
        )
        request = chip.request_lines(
            consumer="inkypi-buttons",
            config=dict.fromkeys(offsets, settings),
        )
        return request, offsets

    def _event_loop(self):
        while self.running:
            try:
                if not self.line_request.wait_edge_events(timeout=0.5):
                    continue
                for event in self.line_request.read_edge_events():
                    action = self.offset_actions.get(event.line_offset)
                    if action:
                        logger.info("Physical button pressed: %s", action)
                        self.submit_action(action)
            except OSError:
                if self.running:
                    logger.exception("Failed while reading physical buttons.")
                return

    def _action_loop(self):
        while self.running:
            try:
                action = self.action_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.action_handler(action)
            except Exception:
                logger.exception("Physical button action failed: %s", action)
            finally:
                with self.action_lock:
                    self.action_pending = False
                self.action_queue.task_done()
