"""
Integración con Neo4j para el grafo de dependencias.
"""
from .neo4j_loader import Neo4jLoader
from .schema import GraphSchema

__all__ = ["Neo4jLoader", "GraphSchema"]
