from __future__ import annotations

import logging
import os
import shlex

from PySide6.QtCore import QObject, QProcess, Signal, Slot

logger = logging.getLogger(__name__)


def resolve_args(template: str, port: str, firmware: str) -> list[str]:
    """Substitute placeholders and split into an argument list."""
    resolved = template.replace("{port}", port).replace("{firmware}", firmware)
    return shlex.split(resolved, posix=os.name != "nt")


class UploadRunner(QObject):
    output_line = Signal(str)      # append a new line
    output_replace = Signal(str)   # replace the current line content
    upload_finished = Signal(int, str)  # exit_code, "normal" | "crashed"
    upload_started = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._cur_line: list[str] = []  # current line as list of chars
        self._cur_pos: int = 0          # cursor position within current line
        self._line_shown: bool = False  # True if current line was emitted via output_replace

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def start(self, executable: str, args: list[str]) -> None:
        if self.is_running():
            logger.warning("Upload already running, ignoring start request")
            return

        self._process = QProcess(self)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        logger.debug("Starting upload: %s %s", executable, args)
        self._process.start(executable, args)
        self.upload_started.emit()

    def cancel(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            logger.debug("Cancelling upload process")
            self._process.kill()

    @Slot()
    def _on_ready_read(self) -> None:
        if not self._process:
            return
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")

        for ch in text:
            if ch == "\n":
                # Line complete — if we already showed this line via
                # output_replace, just advance; otherwise emit content.
                if self._line_shown:
                    self.output_line.emit("")
                else:
                    self.output_line.emit("".join(self._cur_line))
                self._cur_line.clear()
                self._cur_pos = 0
                self._line_shown = False
            elif ch == "\r":
                # Carriage return — move cursor to start of line
                self._cur_pos = 0
            else:
                # Overwrite or append character at cursor position
                if self._cur_pos < len(self._cur_line):
                    self._cur_line[self._cur_pos] = ch
                else:
                    self._cur_line.append(ch)
                self._cur_pos += 1

        # Emit current line state so the UI shows live progress
        if self._cur_line:
            self.output_replace.emit("".join(self._cur_line))
            self._line_shown = True

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._cur_line and not self._line_shown:
            self.output_line.emit("".join(self._cur_line))
        self._cur_line.clear()
        self._cur_pos = 0
        self._line_shown = False

        status = (
            "normal"
            if exit_status == QProcess.ExitStatus.NormalExit
            else "crashed"
        )
        logger.debug("Upload finished: exit_code=%d status=%s", exit_code, status)
        self.upload_finished.emit(exit_code, status)

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start — executable not found or not executable",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error",
        }
        msg = error_messages.get(error, f"Process error: {error}")
        self.output_line.emit(f"[Error: {msg}]")
