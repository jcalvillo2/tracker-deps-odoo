"""
Definición del esquema del grafo en Neo4j.
"""


class GraphSchema:
    """Esquema del grafo de dependencias Odoo."""

    # ========================================================================
    # Node Labels
    # ========================================================================
    NODE_MODULE = "OdooModule"
    NODE_MODEL = "OdooModel"
    NODE_VIEW = "OdooView"
    NODE_FIELD = "OdooField"

    # ========================================================================
    # Relationship Types
    # ========================================================================
    REL_MODULE_DEPENDS = "DEPENDS_ON"
    REL_MODULE_CONTAINS_MODEL = "CONTAINS_MODEL"
    REL_MODULE_CONTAINS_VIEW = "CONTAINS_VIEW"
    REL_MODEL_INHERITS = "INHERITS"
    REL_MODEL_INHERITS_DELEGATION = "INHERITS_DELEGATION"
    REL_MODEL_HAS_FIELD = "HAS_FIELD"
    REL_FIELD_RELATES_TO = "RELATES_TO"
    REL_VIEW_EXTENDS = "EXTENDS"
    REL_VIEW_FOR_MODEL = "VIEW_FOR"

    # ========================================================================
    # Node Properties (for consistency and refactoring safety)
    # ========================================================================

    # Module properties
    PROP_MODULE_NAME = "name"
    PROP_MODULE_VERSION = "version"
    PROP_MODULE_DESCRIPTION = "description"
    PROP_MODULE_AUTHOR = "author"
    PROP_MODULE_CATEGORY = "category"
    PROP_MODULE_PATH = "path"
    PROP_MODULE_INSTALLABLE = "installable"
    PROP_MODULE_AUTO_INSTALL = "auto_install"

    # Model properties
    PROP_MODEL_NAME = "name"
    PROP_MODEL_DESCRIPTION = "description"
    PROP_MODEL_MODULE = "module"
    PROP_MODEL_FILE_PATH = "file_path"
    PROP_MODEL_CLASS_NAME = "class_name"
    PROP_MODEL_TYPE = "model_type"
    PROP_MODEL_IS_ABSTRACT = "is_abstract"
    PROP_MODEL_IS_EXTENSION = "is_extension"
    PROP_MODEL_IS_TRANSIENT = "is_transient"

    # View properties
    PROP_VIEW_XML_ID = "xml_id"
    PROP_VIEW_NAME = "name"
    PROP_VIEW_MODEL = "model"
    PROP_VIEW_TYPE = "view_type"
    PROP_VIEW_MODULE = "module"
    PROP_VIEW_FILE_PATH = "file_path"
    PROP_VIEW_PRIORITY = "priority"

    # Field properties
    PROP_FIELD_MODEL = "model"
    PROP_FIELD_NAME = "name"
    PROP_FIELD_TYPE = "field_type"
    PROP_FIELD_ATTRIBUTES = "attributes"

    @classmethod
    def get_constraints(cls):
        """
        Retorna las constraints y índices para crear en Neo4j.

        Returns:
            Lista de queries Cypher para constraints
        """
        return [
            # Constraints de unicidad
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (m:{cls.NODE_MODULE}) REQUIRE m.name IS UNIQUE",
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (m:{cls.NODE_MODEL}) REQUIRE m.name IS UNIQUE",
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (v:{cls.NODE_VIEW}) REQUIRE v.xml_id IS UNIQUE",
            # Índices para búsquedas
            f"CREATE INDEX IF NOT EXISTS FOR (m:{cls.NODE_MODEL}) ON (m.module)",
            f"CREATE INDEX IF NOT EXISTS FOR (v:{cls.NODE_VIEW}) ON (v.model)",
            f"CREATE INDEX IF NOT EXISTS FOR (f:{cls.NODE_FIELD}) ON (f.field_type)",
        ]

    @classmethod
    def get_cleanup_queries(cls):
        """
        Retorna queries para limpiar el grafo.

        Returns:
            Lista de queries Cypher
        """
        return [
            "MATCH (n) DETACH DELETE n",
        ]
