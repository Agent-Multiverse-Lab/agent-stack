import logging
from datetime import datetime
from pathlib import Path


class DailyFileHandler(logging.FileHandler):
    """按日志发生日期追加文件，跨天时切换到新文件。"""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path.resolve()
        super().__init__(
            self._dated_path(datetime.now()), encoding="utf-8", delay=True
        )

    def _dated_path(self, date: datetime) -> Path:
        return self._log_path.with_name(
            f"{self._log_path.stem}-{date:%Y-%m-%d}{self._log_path.suffix}"
        )

    def emit(self, record: logging.LogRecord) -> None:
        log_path = self._dated_path(datetime.fromtimestamp(record.created))
        if str(log_path) != self.baseFilename:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            self.baseFilename = str(log_path)
        super().emit(record)


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLORS.get(record.levelno)
        if not color:
            return message
        return f"{color}{message}{self.RESET}"


class Logger:
    """日志工具类."""

    def __init__(
        self,
        name: str = "multi-agent-s2c",
        level: int = logging.INFO,
        log_file: str | None = None,
    ) -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if self.logger.handlers:
            return

        log_format = (
            "%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
        )
        formatter = logging.Formatter(
            log_format[0],
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        color_formatter = ColorFormatter(
            log_format[0],
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(color_formatter)
        self.logger.addHandler(stream_handler)

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = DailyFileHandler(log_path)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self.logger.propagate = False

    @staticmethod
    def _with_stacklevel(kwargs: dict) -> dict:
        payload = dict(kwargs)
        payload["stacklevel"] = payload.get("stacklevel", 2)
        return payload

    def debug(self, message: str, *args: object) -> None:
        self.logger.debug(message, *args, **self._with_stacklevel({}))

    def info(self, message: str, *args: object) -> None:
        self.logger.info(message, *args, **self._with_stacklevel({}))

    def warning(self, message: str, *args: object) -> None:
        self.logger.warning(message, *args, **self._with_stacklevel({}))

    def error(self, message: str, *args: object) -> None:
        self.logger.error(message, *args, **self._with_stacklevel({}))

    def exception(self, message: str, *args: object) -> None:
        self.logger.exception(message, *args, **self._with_stacklevel({}))

    def critical(self, message: str, *args: object) -> None:
        self.logger.critical(message, *args, **self._with_stacklevel({}))


Log = Logger
_log_dir = Path(__file__).resolve().parents[2] / "logs"
logger = Logger(name="s2c", log_file=str(_log_dir / "s2c.log"))
