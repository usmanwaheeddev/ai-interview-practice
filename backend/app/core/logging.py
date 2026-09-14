import logging
import sys

import structlog

_NOISY_THIRD_PARTY_LOGGERS = (
    "boto3",
    "botocore",
    "urllib3",
    "s3transfer",
    "httpx",
    "httpcore",
    "huggingface_hub",
    "filelock",
    "piper",
    "faster_whisper",
)


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )

    # DEBUG on our own loggers is useful; DEBUG on boto3's internals is a
    # wall of per-request signing noise that drowns everything else out.
    for name in _NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
