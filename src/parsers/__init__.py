"""
Parsers para código Python y XML de Odoo.
"""
from .model_parser import ModelParser, OdooModel
from .view_parser import ViewParser, OdooView

__all__ = ["ModelParser", "OdooModel", "ViewParser", "OdooView"]
