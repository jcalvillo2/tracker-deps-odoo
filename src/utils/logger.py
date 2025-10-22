"""
Sistema de logging estructurado.
"""
import logging
import sys
from pathlib import Path


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Path = None
) -> logging.Logger:
    """
    Configura un logger con formato estructurado.

    Args:
        name: Nombre del logger
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Ruta opcional al archivo de log

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger

    # Formato estructurado
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler opcional para archivo
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger por nombre (reutilizable).

    Args:
        name: Nombre del logger

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
