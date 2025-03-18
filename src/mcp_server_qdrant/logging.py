"""
Structured logging configuration for the MCP Server Qdrant.
"""
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

# Configure default logger
logger = logging.getLogger("mcp_server_qdrant")


class CorrelationIdFilter(logging.Filter):
    """
    Filter that adds correlation_id to LogRecord instances.
    """
    _correlation_id: Optional[str] = None

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = self._correlation_id or "no_correlation_id"
        return True

    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Set the correlation ID for the current context."""
        cls._correlation_id = correlation_id

    @classmethod
    def clear_correlation_id(cls) -> None:
        """Clear the correlation ID for the current context."""
        cls._correlation_id = None

    @classmethod
    @contextmanager
    def correlation_id(cls, correlation_id: Optional[str] = None) -> Generator[str, None, None]:
        """
        Context manager that sets a correlation ID for the duration of the context.
        If no correlation ID is provided, a random UUID is generated.
        """
        generated_id = correlation_id or str(uuid.uuid4())
        try:
            cls.set_correlation_id(generated_id)
            yield generated_id
        finally:
            cls.clear_correlation_id()


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the log record.
    """
    def __init__(
        self,
        fmt_dict: Optional[Dict[str, Any]] = None,
        time_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        """
        Initialize a new JSONFormatter.
        """
        super().__init__()
        self.fmt_dict = fmt_dict if fmt_dict is not None else {
            "timestamp": "%(asctime)s",
            "level": "%(levelname)s",
            "name": "%(name)s",
            "correlation_id": "%(correlation_id)s",
            "message": "%(message)s",
        }
        self.time_format = time_format

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record as JSON."""
        record.asctime = self.formatTime(record, self.time_format)
        log_dict = {}
        for key, value in self.fmt_dict.items():
            try:
                log_dict[key] = value % record.__dict__
            except (KeyError, TypeError):
                log_dict[key] = value

        # Add exception information if available
        if record.exc_info:
            log_dict["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # Add additional fields from record
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_dict.update(record.extra)

        return json.dumps(log_dict)


def configure_logging(
    level: int = logging.INFO,
    json_format: bool = True,
    include_correlation_id: bool = True,
) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: The minimum logging level.
        json_format: Whether to output logs in JSON format.
        include_correlation_id: Whether to include correlation IDs in logs.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Add correlation ID filter if requested
    if include_correlation_id:
        correlation_id_filter = CorrelationIdFilter()
        console_handler.addFilter(correlation_id_filter)

    # Set formatter based on format preference
    if json_format:
        formatter = JSONFormatter()
    else:
        log_format = "%(asctime)s | %(levelname)s | %(name)s | %(correlation_id)s | %(message)s" if include_correlation_id else "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        formatter = logging.Formatter(log_format)

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# Helper functions for structured logging
def log_with_context(
    logger_instance: logging.Logger,
    level: int,
    msg: str,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Any = None,
) -> None:
    """
    Log a message with additional context.
    
    Args:
        logger_instance: The logger to use.
        level: The log level.
        msg: The log message.
        context: Additional context to include in the log record.
        exc_info: Exception information to include in the log record.
    """
    if context is None:
        context = {}
    extra = {"extra": context}
    logger_instance.log(level, msg, extra=extra, exc_info=exc_info)


def debug(logger_instance: logging.Logger, msg: str, context: Optional[Dict[str, Any]] = None) -> None:
    """Log a debug message with context."""
    log_with_context(logger_instance, logging.DEBUG, msg, context)


def info(logger_instance: logging.Logger, msg: str, context: Optional[Dict[str, Any]] = None) -> None:
    """Log an info message with context."""
    log_with_context(logger_instance, logging.INFO, msg, context)


def warning(logger_instance: logging.Logger, msg: str, context: Optional[Dict[str, Any]] = None) -> None:
    """Log a warning message with context."""
    log_with_context(logger_instance, logging.WARNING, msg, context)


def error(
    logger_instance: logging.Logger,
    msg: str,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Any = None,
) -> None:
    """Log an error message with context."""
    log_with_context(logger_instance, logging.ERROR, msg, context, exc_info)


def critical(
    logger_instance: logging.Logger,
    msg: str,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Any = None,
) -> None:
    """Log a critical message with context."""
    log_with_context(logger_instance, logging.CRITICAL, msg, context, exc_info)
