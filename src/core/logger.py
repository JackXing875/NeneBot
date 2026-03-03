"""Structured logging configuration."""
import logging
import sys

def setup_logger():
    """Initializes the global logger with standard industrial formatting."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    # Return the root logger
    return logging.getLogger("NeneBot")