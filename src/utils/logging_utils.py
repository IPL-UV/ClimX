import logging
import sys

def setup_logger(level=logging.INFO):
    """
    Set up the root logger to a specified level.

    This function configures the root logger to output messages to the console
    (standard output). It removes any existing handlers to prevent duplicate
    log messages and sets up a new handler with a clear, readable format.

    Args:
        level (int, optional): The logging level to set for the logger.
                               Defaults to logging.INFO.
    """
    # Get the root logger
    logger = logging.getLogger()
    
    # Remove any existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    # Set the new logging level
    logger.setLevel(level)

    # Create a handler to write messages to standard output
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Create a formatter for clear, readable log messages
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    logger.info(f"Logger configured with level: {logging.getLevelName(level)}")
