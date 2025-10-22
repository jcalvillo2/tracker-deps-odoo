"""
Motor de consultas predefinidas y ad-hoc sobre el grafo.
"""
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from config import Config
from src.graph.schema import GraphSchema


class QueryEngine:
    """Motor de consultas sobre el grafo de dependencias Odoo."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """
        Inicializa el motor de consultas.

        Args:
            uri: URI de Neo4j
            user: Usuario
            password: Contraseña
        """
        self.uri = uri or Config.NEO4J_URI
        self.user = user or Config.NEO4J_USER
        self.password = password or Config.NEO4J_PASSWORD

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.schema = GraphSchema()

    def close(self):
        """Cierra la conexión."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        """Context manager enter."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def get_model_children(self, model_name: str) -> List[Dict]:
        """
        Obtiene todos los modelos que heredan de un modelo dado.

        Args:
            model_name: Nombre del modelo padre

        Returns:
            Lista de modelos hijos
        """
        query = f"""
        MATCH (child:{self.schema.NODE_MODEL})-[:{self.schema.REL_MODEL_INHERITS}]->(parent:{self.schema.NODE_MODEL} {{name: $model_name}})
        RETURN child.name as name, child.module as module, child.model_type as model_type
        ORDER BY child.name
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            return [dict(record) for record in result]

    def get_model_parents(self, model_name: str) -> List[Dict]:
        """
        Obtiene todos los modelos padre de un modelo dado.

        Args:
            model_name: Nombre del modelo hijo

        Returns:
            Lista de modelos padre
        """
        query = f"""
        MATCH (child:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_INHERITS}]->(parent:{self.schema.NODE_MODEL})
        RETURN parent.name as name, parent.module as module, parent.model_type as model_type
        ORDER BY parent.name
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            return [dict(record) for record in result]

    def get_model_hierarchy(self, model_name: str, depth: int = 5) -> Dict:
        """
        Obtiene la jerarquía completa de herencia de un modelo.

        Args:
            model_name: Nombre del modelo
            depth: Profundidad máxima de búsqueda

        Returns:
            Diccionario con jerarquía completa
        """
        query = f"""
        MATCH path = (child:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_INHERITS}*..{depth}]->(parent:{self.schema.NODE_MODEL})
        WITH child, parent, path
        RETURN child.name as child, parent.name as parent, length(path) as depth
        ORDER BY depth, parent
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            return {"model": model_name, "parents": [dict(record) for record in result]}

    def get_views_for_model(self, model_name: str) -> List[Dict]:
        """
        Obtiene todas las vistas de un modelo.

        Args:
            model_name: Nombre del modelo

        Returns:
            Lista de vistas
        """
        query = f"""
        MATCH (v:{self.schema.NODE_VIEW})-[:{self.schema.REL_VIEW_FOR_MODEL}]->(m:{self.schema.NODE_MODEL} {{name: $model_name}})
        RETURN v.xml_id as xml_id, v.name as name, v.view_type as view_type, v.module as module
        ORDER BY v.view_type, v.priority
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            return [dict(record) for record in result]

    def get_view_extensions(self, view_xml_id: str) -> List[Dict]:
        """
        Obtiene todas las vistas que extienden una vista dada.

        Args:
            view_xml_id: XML ID de la vista padre

        Returns:
            Lista de vistas que la extienden
        """
        query = f"""
        MATCH (child:{self.schema.NODE_VIEW})-[:{self.schema.REL_VIEW_EXTENDS}]->(parent:{self.schema.NODE_VIEW} {{xml_id: $view_xml_id}})
        RETURN child.xml_id as xml_id, child.name as name, child.module as module
        ORDER BY child.xml_id
        """

        with self.driver.session() as session:
            result = session.run(query, view_xml_id=view_xml_id)
            return [dict(record) for record in result]

    def get_model_fields(self, model_name: str, field_type: str = None) -> List[Dict]:
        """
        Obtiene los campos de un modelo.

        Args:
            model_name: Nombre del modelo
            field_type: Tipo de campo (opcional, para filtrar)

        Returns:
            Lista de campos
        """
        if field_type:
            query = f"""
            MATCH (m:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f:{self.schema.NODE_FIELD} {{field_type: $field_type}})
            RETURN f.name as name, f.field_type as field_type
            ORDER BY f.name
            """
            params = {"model_name": model_name, "field_type": field_type}
        else:
            query = f"""
            MATCH (m:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f:{self.schema.NODE_FIELD})
            RETURN f.name as name, f.field_type as field_type
            ORDER BY f.name
            """
            params = {"model_name": model_name}

        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def get_model_relations(self, model_name: str) -> List[Dict]:
        """
        Obtiene todos los modelos relacionados a través de campos.

        Args:
            model_name: Nombre del modelo

        Returns:
            Lista de modelos relacionados
        """
        query = f"""
        MATCH (m:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f:{self.schema.NODE_FIELD})
        MATCH (f)-[:{self.schema.REL_FIELD_RELATES_TO}]->(target:{self.schema.NODE_MODEL})
        RETURN f.name as field_name, f.field_type as field_type, target.name as target_model
        ORDER BY f.name
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            return [dict(record) for record in result]

    def get_module_dependencies(self, module_name: str) -> List[Dict]:
        """
        Obtiene las dependencias de un módulo.

        Args:
            module_name: Nombre del módulo

        Returns:
            Lista de módulos de los que depende
        """
        query = f"""
        MATCH (m:{self.schema.NODE_MODULE} {{name: $module_name}})-[:{self.schema.REL_MODULE_DEPENDS}]->(dep:{self.schema.NODE_MODULE})
        RETURN dep.name as name, dep.version as version
        ORDER BY dep.name
        """

        with self.driver.session() as session:
            result = session.run(query, module_name=module_name)
            return [dict(record) for record in result]

    def get_module_dependents(self, module_name: str) -> List[Dict]:
        """
        Obtiene los módulos que dependen de un módulo dado.

        Args:
            module_name: Nombre del módulo

        Returns:
            Lista de módulos dependientes
        """
        query = f"""
        MATCH (dependent:{self.schema.NODE_MODULE})-[:{self.schema.REL_MODULE_DEPENDS}]->(m:{self.schema.NODE_MODULE} {{name: $module_name}})
        RETURN dependent.name as name, dependent.version as version
        ORDER BY dependent.name
        """

        with self.driver.session() as session:
            result = session.run(query, module_name=module_name)
            return [dict(record) for record in result]

    def search_models(self, search_term: str) -> List[Dict]:
        """
        Busca modelos por nombre (búsqueda parcial).

        Args:
            search_term: Término de búsqueda

        Returns:
            Lista de modelos que coinciden
        """
        query = f"""
        MATCH (m:{self.schema.NODE_MODEL})
        WHERE m.name CONTAINS $search_term
        RETURN m.name as name, m.module as module, m.description as description
        ORDER BY m.name
        LIMIT 50
        """

        with self.driver.session() as session:
            result = session.run(query, search_term=search_term)
            return [dict(record) for record in result]

    def get_model_impact(self, model_name: str) -> Dict:
        """
        Analiza el impacto de un modelo (cuántos modelos y vistas dependen de él).

        Args:
            model_name: Nombre del modelo

        Returns:
            Diccionario con análisis de impacto
        """
        query = f"""
        MATCH (m:{self.schema.NODE_MODEL} {{name: $model_name}})
        OPTIONAL MATCH (child:{self.schema.NODE_MODEL})-[:{self.schema.REL_MODEL_INHERITS}]->(m)
        OPTIONAL MATCH (v:{self.schema.NODE_VIEW})-[:{self.schema.REL_VIEW_FOR_MODEL}]->(m)
        OPTIONAL MATCH (m)-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f:{self.schema.NODE_FIELD})-[:{self.schema.REL_FIELD_RELATES_TO}]->(related:{self.schema.NODE_MODEL})
        WITH m,
             count(DISTINCT child) as children_count,
             count(DISTINCT v) as views_count,
             count(DISTINCT related) as related_models_count
        RETURN m.name as model,
               children_count,
               views_count,
               related_models_count
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            record = result.single()
            return dict(record) if record else {}

    def execute_custom_query(self, cypher_query: str, params: Dict = None) -> List[Dict]:
        """
        Ejecuta una consulta Cypher personalizada.

        Args:
            cypher_query: Query Cypher
            params: Parámetros de la query

        Returns:
            Lista de resultados
        """
        with self.driver.session() as session:
            result = session.run(cypher_query, **(params or {}))
            return [dict(record) for record in result]
