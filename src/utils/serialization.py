"""
Utilidades para serialización de datos a formatos compatibles con Neo4j.
"""
import json
from typing import Any, Dict, List


def serialize_for_neo4j(value: Any) -> Any:
    """
    Convierte valores de Python a tipos compatibles con Neo4j.

    Neo4j no puede almacenar colecciones anidadas, así que las convertimos
    a strings JSON.

    Args:
        value: Valor Python a convertir

    Returns:
        Valor compatible con Neo4j
    """
    if value is None:
        return None
    elif isinstance(value, (list, dict)):
        # Convertir colecciones anidadas a JSON string
        return json.dumps(value)
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (int, float, str)):
        return value
    else:
        # Convertir otros tipos a string
        return str(value)


def prepare_batch_for_neo4j(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepara un batch de items para inserción en Neo4j.

    Serializa todos los valores anidados a formatos compatibles.

    Args:
        items: Lista de diccionarios con datos

    Returns:
        Lista de diccionarios con valores serializados
    """
    prepared = []
    for item in items:
        prepared_item = {}
        for key, value in item.items():
            prepared_item[key] = serialize_for_neo4j(value)
        prepared.append(prepared_item)
    return prepared
