import logging
import sys


def setup_logger():
    logger = logging.getLogger('RTPM_APP')
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if logger.hasHandlers():
        return logger

    # Create handlers
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    file_handler = logging.FileHandler('rtpm_app.log')
    file_handler.setLevel(logging.DEBUG)

    # Create formatters and add it to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stdout_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)

    return logger

# Setup logger instance
logger = setup_logger()
