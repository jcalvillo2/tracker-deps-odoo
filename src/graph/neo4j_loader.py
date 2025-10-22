"""
Loader para cargar datos en Neo4j de forma eficiente.
Versión mejorada con logging estructurado y mejor manejo de errores.
"""
import json
import logging
from typing import List, Dict, Optional
from neo4j import GraphDatabase, Session
from config import Config
from .schema import GraphSchema
from ..utils.logger import setup_logger
from ..utils.serialization import serialize_for_neo4j


class Neo4jLoader:
    """Cargador de datos a Neo4j con batch processing."""

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        log_level: int = logging.WARNING
    ):
        """
        Inicializa la conexión a Neo4j.

        Args:
            uri: URI de Neo4j
            user: Usuario
            password: Contraseña
            log_level: Nivel de logging (por defecto WARNING para no interferir con rich)
        """
        self.uri = uri or Config.NEO4J_URI
        self.user = user or Config.NEO4J_USER
        self.password = password or Config.NEO4J_PASSWORD
        self.batch_size = Config.BATCH_SIZE

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self.schema = GraphSchema()

        # Logger estructurado (nivel WARNING para no interferir con rich console)
        self.logger = setup_logger(__name__, level=log_level)

        # Métricas de operación
        self.metrics = {
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": 0,
            "batches_processed": 0
        }

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

    def setup_schema(self):
        """Configura constraints e índices."""
        with self.driver.session() as session:
            for query in self.schema.get_constraints():
                try:
                    session.run(query)
                except Exception as e:
                    print(f"Warning creando constraint: {e}")

    def clear_graph(self):
        """Limpia todo el grafo."""
        with self.driver.session() as session:
            for query in self.schema.get_cleanup_queries():
                session.run(query)

    def load_modules(self, modules: List[Dict]):
        """
        Carga módulos en el grafo.

        Args:
            modules: Lista de diccionarios con datos de módulos
        """
        query = f"""
        UNWIND $modules AS module
        MERGE (m:{self.schema.NODE_MODULE} {{name: module.name}})
        SET m.version = module.version,
            m.description = module.description,
            m.author = module.author,
            m.category = module.category,
            m.path = module.path,
            m.installable = module.installable,
            m.auto_install = module.auto_install
        """

        self._batch_execute(query, modules, "modules", "módulos")

        # Cargar dependencias entre módulos
        self._load_module_dependencies(modules)

    def _load_module_dependencies(self, modules: List[Dict]):
        """Carga relaciones de dependencia entre módulos."""
        dependencies = []
        for module in modules:
            for dep in module.get("depends", []):
                dependencies.append({"from": module["name"], "to": dep})

        if not dependencies:
            return

        query = f"""
        UNWIND $deps AS dep
        MATCH (m1:{self.schema.NODE_MODULE} {{name: dep.from}})
        MATCH (m2:{self.schema.NODE_MODULE} {{name: dep.to}})
        MERGE (m1)-[:{self.schema.REL_MODULE_DEPENDS}]->(m2)
        """

        self._batch_execute(query, dependencies, "deps", "dependencias de módulos")

    def load_organized_data(self, data: Dict):
        """
        Carga datos pre-organizados en orden óptimo.
        Patrón ETL: Los datos ya están extraídos y transformados,
        solo falta cargarlos en el orden correcto.

        Args:
            data: Diccionario con datos organizados por tipo
        """
        import time

        print("\n[FASE 1: NODOS] Creando nodos sin relaciones...")
        start = time.time()

        # 1. Módulos (base de todo)
        print(f"\n→ Cargando {len(data['modules'])} módulos...")
        query = f"""
        UNWIND $modules AS module
        MERGE (m:{self.schema.NODE_MODULE} {{name: module.name}})
        SET m.version = module.version,
            m.description = module.description,
            m.author = module.author,
            m.category = module.category,
            m.path = module.path,
            m.installable = module.installable,
            m.auto_install = module.auto_install
        """
        self._batch_execute(query, data["modules"], "modules", "módulos")

        # 2. Modelos (independientes)
        print(f"\n→ Cargando {len(data['models'])} modelos...")
        query = f"""
        UNWIND $models AS model
        MERGE (m:{self.schema.NODE_MODEL} {{name: model.name}})
        SET m.description = model.description,
            m.module = model.module,
            m.file_path = model.file_path,
            m.class_name = model.class_name,
            m.model_type = model.model_type,
            m.is_abstract = model.is_abstract,
            m.is_extension = model.is_extension,
            m.is_transient = model.is_transient
        """
        self._batch_execute(query, data["models"], "models", "modelos")

        # 3. Vistas (independientes)
        print(f"\n→ Cargando {len(data['views'])} vistas...")
        query = f"""
        UNWIND $views AS view
        MERGE (v:{self.schema.NODE_VIEW} {{xml_id: view.xml_id}})
        SET v.name = view.name,
            v.model = view.model,
            v.view_type = view.view_type,
            v.module = view.module,
            v.file_path = view.file_path,
            v.priority = view.priority
        """
        self._batch_execute(query, data["views"], "views", "vistas")

        # 4. Campos (independientes - sin related_model aún)
        print(f"\n→ Cargando {len(data['fields'])} campos...")
        query = f"""
        UNWIND $fields AS field
        MERGE (f:{self.schema.NODE_FIELD} {{model: field.model_name, name: field.field_name}})
        SET f.field_type = field.field_type,
            f.attributes = field.attributes
        """
        # Convertir attributes a JSON
        fields_with_json = []
        for field in data["fields"]:
            field_copy = field.copy()
            field_copy["attributes"] = json.dumps(field.get("attributes", {}))
            fields_with_json.append(field_copy)

        self._batch_execute(query, fields_with_json, "fields", "campos")

        nodes_time = time.time() - start
        print(f"\n✓ Nodos creados en {nodes_time:.2f}s\n")

        print("[FASE 2: RELACIONES] Creando relaciones entre nodos...")
        start = time.time()

        # 5. Dependencias de módulos
        if data["module_dependencies"]:
            print(f"\n→ Creando {len(data['module_dependencies'])} dependencias de módulos...")
            query = f"""
            UNWIND $deps AS dep
            MATCH (m1:{self.schema.NODE_MODULE} {{name: dep.from}})
            MATCH (m2:{self.schema.NODE_MODULE} {{name: dep.to}})
            MERGE (m1)-[:{self.schema.REL_MODULE_DEPENDS}]->(m2)
            """
            self._batch_execute(query, data["module_dependencies"], "deps", "dependencias módulo")

        # 6. Relaciones modelo→módulo
        if data["model_module_rels"]:
            print(f"\n→ Creando {len(data['model_module_rels'])} relaciones modelo→módulo...")
            query = f"""
            UNWIND $rels AS rel
            MATCH (m:{self.schema.NODE_MODEL} {{name: rel.model}})
            MATCH (mod:{self.schema.NODE_MODULE} {{name: rel.module}})
            MERGE (mod)-[:{self.schema.REL_MODULE_CONTAINS_MODEL}]->(m)
            """
            self._batch_execute(query, data["model_module_rels"], "rels", "relaciones modelo→módulo")

        # 7. Herencias de modelos
        if data["model_inheritances"]:
            print(f"\n→ Creando {len(data['model_inheritances'])} herencias de modelos...")
            query = f"""
            UNWIND $inh AS inh
            MATCH (child:{self.schema.NODE_MODEL} {{name: inh.child}})
            MERGE (parent:{self.schema.NODE_MODEL} {{name: inh.parent}})
            MERGE (child)-[:{self.schema.REL_MODEL_INHERITS}]->(parent)
            """
            self._batch_execute(query, data["model_inheritances"], "inh", "herencias modelo")

        # 8. Delegaciones de modelos
        if data["model_delegations"]:
            print(f"\n→ Creando {len(data['model_delegations'])} delegaciones de modelos...")
            query = f"""
            UNWIND $dels AS del
            MATCH (child:{self.schema.NODE_MODEL} {{name: del.child}})
            MERGE (parent:{self.schema.NODE_MODEL} {{name: del.parent}})
            MERGE (child)-[r:{self.schema.REL_MODEL_INHERITS_DELEGATION}]->(parent)
            SET r.field = del.field
            """
            self._batch_execute(query, data["model_delegations"], "dels", "delegaciones modelo")

        # 9. Relaciones campo→modelo
        if data["field_model_rels"]:
            print(f"\n→ Creando {len(data['field_model_rels'])} relaciones campo→modelo...")
            query = f"""
            UNWIND $rels AS rel
            MATCH (m:{self.schema.NODE_MODEL} {{name: rel.model_name}})
            MATCH (f:{self.schema.NODE_FIELD} {{model: rel.model_name, name: rel.field_name}})
            MERGE (m)-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f)
            """
            self._batch_execute(query, data["field_model_rels"], "rels", "relaciones campo→modelo")

        # 10. Referencias de campos (Many2one, etc)
        if data["field_references"]:
            print(f"\n→ Creando {len(data['field_references'])} referencias de campos...")
            query = f"""
            UNWIND $refs AS ref
            MATCH (f:{self.schema.NODE_FIELD} {{model: ref.model_name, name: ref.field_name}})
            MERGE (target:{self.schema.NODE_MODEL} {{name: ref.related_model}})
            MERGE (f)-[:{self.schema.REL_FIELD_RELATES_TO}]->(target)
            """
            self._batch_execute(query, data["field_references"], "refs", "referencias campo")

        # 11. Relaciones vista→módulo
        if data["view_module_rels"]:
            print(f"\n→ Creando {len(data['view_module_rels'])} relaciones vista→módulo...")
            query = f"""
            UNWIND $rels AS rel
            MATCH (v:{self.schema.NODE_VIEW} {{xml_id: rel.view_xml_id}})
            MATCH (mod:{self.schema.NODE_MODULE} {{name: rel.module}})
            MERGE (mod)-[:{self.schema.REL_MODULE_CONTAINS_VIEW}]->(v)
            """
            self._batch_execute(query, data["view_module_rels"], "rels", "relaciones vista→módulo")

        # 12. Relaciones vista→modelo
        if data["view_model_rels"]:
            print(f"\n→ Creando {len(data['view_model_rels'])} relaciones vista→modelo...")
            query = f"""
            UNWIND $rels AS rel
            MATCH (v:{self.schema.NODE_VIEW} {{xml_id: rel.view_xml_id}})
            MATCH (m:{self.schema.NODE_MODEL} {{name: rel.model}})
            MERGE (v)-[:{self.schema.REL_VIEW_FOR_MODEL}]->(m)
            """
            self._batch_execute(query, data["view_model_rels"], "rels", "relaciones vista→modelo")

        # 13. Herencias de vistas
        if data["view_inheritances"]:
            print(f"\n→ Creando {len(data['view_inheritances'])} herencias de vistas...")
            query = f"""
            UNWIND $inh AS inh
            MATCH (child:{self.schema.NODE_VIEW} {{xml_id: inh.child}})
            MERGE (parent:{self.schema.NODE_VIEW} {{xml_id: inh.parent}})
            MERGE (child)-[:{self.schema.REL_VIEW_EXTENDS}]->(parent)
            """
            self._batch_execute(query, data["view_inheritances"], "inh", "herencias vista")

        rels_time = time.time() - start
        total_time = nodes_time + rels_time

        print(f"\n✓ Relaciones creadas en {rels_time:.2f}s")
        print(f"\n{'='*60}")
        print(f"RESUMEN DE CARGA:")
        print(f"  • Tiempo nodos: {nodes_time:.2f}s")
        print(f"  • Tiempo relaciones: {rels_time:.2f}s")
        print(f"  • Tiempo total: {total_time:.2f}s")
        print(f"{'='*60}\n")

    def load_models(self, models: List[Dict]):
        """
        Carga modelos en el grafo.

        Args:
            models: Lista de diccionarios con datos de modelos
        """
        # Filtrar modelos inválidos (sin nombre)
        valid_models = [m for m in models if m.get("name")]
        invalid_count = len(models) - len(valid_models)

        if invalid_count > 0:
            print(f"Warning: {invalid_count} modelos sin nombre válido fueron descartados")

        if not valid_models:
            print("Warning: No hay modelos válidos para cargar")
            return

        # Primero crear nodos de modelos (sin relaciones)
        query = f"""
        UNWIND $models AS model
        MERGE (m:{self.schema.NODE_MODEL} {{name: model.name}})
        SET m.description = model.description,
            m.module = model.module,
            m.file_path = model.file_path,
            m.class_name = model.class_name,
            m.model_type = model.model_type,
            m.is_abstract = model.is_abstract,
            m.is_extension = model.is_extension,
            m.is_transient = model.is_transient
        """

        self._batch_execute(query, valid_models, "models", "nodos de modelos")

        # Crear relaciones módulo->modelo en query separada (más rápido)
        rel_query = f"""
        UNWIND $models AS model
        MATCH (m:{self.schema.NODE_MODEL} {{name: model.name}})
        MATCH (mod:{self.schema.NODE_MODULE} {{name: model.module}})
        MERGE (mod)-[:{self.schema.REL_MODULE_CONTAINS_MODEL}]->(m)
        """

        self._batch_execute(rel_query, valid_models, "models", "relaciones módulo→modelo")

        # Cargar herencias
        self._load_model_inheritance(valid_models)

        # Cargar campos
        self._load_model_fields(valid_models)

    def _load_model_inheritance(self, models: List[Dict]):
        """Carga relaciones de herencia entre modelos."""
        # Herencia simple (_inherit)
        inheritances = []
        for model in models:
            for parent in model.get("inherits", []):
                inheritances.append({"child": model["name"], "parent": parent})

        if inheritances:
            query = f"""
            UNWIND $inherits AS inh
            MATCH (child:{self.schema.NODE_MODEL} {{name: inh.child}})
            MERGE (parent:{self.schema.NODE_MODEL} {{name: inh.parent}})
            MERGE (child)-[:{self.schema.REL_MODEL_INHERITS}]->(parent)
            """
            self._batch_execute(query, inheritances, "inherits", "herencias de modelos (_inherit)")

        # Herencia por delegación (_inherits)
        delegations = []
        for model in models:
            for parent, field in model.get("inherits_models", {}).items():
                delegations.append(
                    {"child": model["name"], "parent": parent, "field": field}
                )

        if delegations:
            query = f"""
            UNWIND $dels AS del
            MATCH (child:{self.schema.NODE_MODEL} {{name: del.child}})
            MERGE (parent:{self.schema.NODE_MODEL} {{name: del.parent}})
            MERGE (child)-[r:{self.schema.REL_MODEL_INHERITS_DELEGATION}]->(parent)
            SET r.field = del.field
            """
            self._batch_execute(query, delegations, "dels", "delegaciones de modelos (_inherits)")

    def _load_model_fields(self, models: List[Dict]):
        """Carga campos de modelos y sus relaciones."""
        fields_data = []

        for model in models:
            for field in model.get("fields", []):
                # Convertir attributes dict a JSON string para Neo4j
                attributes = field.get("attributes", {})
                attributes_json = json.dumps(attributes) if attributes else "{}"

                field_data = {
                    "model_name": model["name"],
                    "field_name": field["name"],
                    "field_type": field["field_type"],
                    "related_model": field.get("related_model"),
                    "attributes": attributes_json,
                }
                fields_data.append(field_data)

        if not fields_data:
            return

        # Crear nodos de campos (sin relaciones)
        query = f"""
        UNWIND $fields AS field
        MERGE (f:{self.schema.NODE_FIELD} {{model: field.model_name, name: field.field_name}})
        SET f.field_type = field.field_type,
            f.attributes = field.attributes
        """

        self._batch_execute(query, fields_data, "fields", "nodos de campos")

        # Crear relaciones modelo->campo
        rel_query = f"""
        UNWIND $fields AS field
        MATCH (m:{self.schema.NODE_MODEL} {{name: field.model_name}})
        MATCH (f:{self.schema.NODE_FIELD} {{model: field.model_name, name: field.field_name}})
        MERGE (m)-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f)
        """

        self._batch_execute(rel_query, fields_data, "fields", "relaciones modelo→campo")

        # Crear relaciones entre campos y modelos relacionados
        relational_fields = [f for f in fields_data if f["related_model"]]

        if relational_fields:
            query = f"""
            UNWIND $fields AS field
            MATCH (f:{self.schema.NODE_FIELD} {{model: field.model_name, name: field.field_name}})
            MERGE (target:{self.schema.NODE_MODEL} {{name: field.related_model}})
            MERGE (f)-[:{self.schema.REL_FIELD_RELATES_TO}]->(target)
            """
            self._batch_execute(query, relational_fields, "fields", "relaciones campo→modelo (Many2one, etc)")

    def load_views(self, views: List[Dict]):
        """
        Carga vistas en el grafo.

        Args:
            views: Lista de diccionarios con datos de vistas
        """
        # Filtrar vistas inválidas (sin xml_id o model)
        valid_views = [v for v in views if v.get("xml_id") and v.get("model")]
        invalid_count = len(views) - len(valid_views)

        if invalid_count > 0:
            print(f"Warning: {invalid_count} vistas sin xml_id o model válido fueron descartadas")

        if not valid_views:
            print("Warning: No hay vistas válidas para cargar")
            return

        # Crear nodos de vistas (sin relaciones)
        query = f"""
        UNWIND $views AS view
        MERGE (v:{self.schema.NODE_VIEW} {{xml_id: view.xml_id}})
        SET v.name = view.name,
            v.model = view.model,
            v.view_type = view.view_type,
            v.module = view.module,
            v.file_path = view.file_path,
            v.priority = view.priority
        """

        self._batch_execute(query, valid_views, "views", "nodos de vistas")

        # Crear relaciones módulo->vista
        rel_module_query = f"""
        UNWIND $views AS view
        MATCH (v:{self.schema.NODE_VIEW} {{xml_id: view.xml_id}})
        MATCH (mod:{self.schema.NODE_MODULE} {{name: view.module}})
        MERGE (mod)-[:{self.schema.REL_MODULE_CONTAINS_VIEW}]->(v)
        """

        self._batch_execute(rel_module_query, valid_views, "views", "relaciones módulo→vista")

        # Crear relaciones vista->modelo
        rel_model_query = f"""
        UNWIND $views AS view
        MATCH (v:{self.schema.NODE_VIEW} {{xml_id: view.xml_id}})
        MATCH (m:{self.schema.NODE_MODEL} {{name: view.model}})
        MERGE (v)-[:{self.schema.REL_VIEW_FOR_MODEL}]->(m)
        """

        self._batch_execute(rel_model_query, valid_views, "views", "relaciones vista→modelo")

        # Cargar herencias de vistas
        self._load_view_inheritance(valid_views)

    def _load_view_inheritance(self, views: List[Dict]):
        """Carga relaciones de herencia entre vistas."""
        inheritances = []
        for view in views:
            if view.get("inherit_id"):
                inheritances.append(
                    {"child": view["xml_id"], "parent": view["inherit_id"]}
                )

        if not inheritances:
            return

        query = f"""
        UNWIND $inherits AS inh
        MATCH (child:{self.schema.NODE_VIEW} {{xml_id: inh.child}})
        MERGE (parent:{self.schema.NODE_VIEW} {{xml_id: inh.parent}})
        MERGE (child)-[:{self.schema.REL_VIEW_EXTENDS}]->(parent)
        """

        self._batch_execute(query, inheritances, "inherits", "herencias de vistas (inherit_id)")

    def _batch_execute(
        self,
        query: str,
        data: List[Dict],
        param_name: str,
        description: str = "items"
    ) -> Dict[str, int]:
        """
        Ejecuta una query en batches para optimizar performance.
        Hace commit cada batch para evitar transacciones demasiado grandes.

        Args:
            query: Query Cypher
            data: Datos a procesar
            param_name: Nombre del parámetro en la query
            description: Descripción para el contador de progreso

        Returns:
            Diccionario con métricas de la operación
        """
        if not data:
            return {"processed": 0, "errors": 0}

        total_items = len(data)
        total_batches = (total_items + self.batch_size - 1) // self.batch_size
        errors = 0
        processed = 0

        print(f"  Cargando {total_items} {description} en {total_batches} batches...")
        self.logger.info(f"Starting batch operation: {description} ({total_items} items, {total_batches} batches)")

        with self.driver.session() as session:
            # Ejecutar cada batch en su propia transacción
            # Esto evita bloqueos con datasets grandes
            for batch_num, i in enumerate(range(0, len(data), self.batch_size), 1):
                batch = data[i : i + self.batch_size]

                try:
                    with session.begin_transaction() as tx:
                        result = tx.run(query, {param_name: batch})
                        tx.commit()
                        processed += len(batch)
                        self.metrics["batches_processed"] += 1

                except Exception as e:
                    errors += len(batch)
                    self.metrics["errors"] += 1
                    self.logger.error(
                        f"Error en batch {batch_num}/{total_batches} de {description}: {str(e)}"
                    )
                    # Continuar con el siguiente batch en lugar de fallar completamente
                    continue

                # Mostrar progreso cada 10% o cada batch si son pocos
                if batch_num % max(1, total_batches // 10) == 0 or batch_num == total_batches:
                    progress_pct = (batch_num / total_batches) * 100
                    print(f"    {description}: {batch_num}/{total_batches} batches ({progress_pct:.0f}%)")

        if errors > 0:
            self.logger.warning(f"Completed {description} with {errors} errors out of {total_items} items")
        else:
            self.logger.info(f"Successfully completed {description}: {processed} items")

        return {"processed": processed, "errors": errors}

    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas del grafo.

        Returns:
            Diccionario con estadísticas
        """
        try:
            with self.driver.session() as session:
                # Queries separadas para evitar producto cartesiano
                stats = {}

                # Contar módulos
                result = session.run(f"MATCH (n:{self.schema.NODE_MODULE}) RETURN count(n) as count")
                stats["modules"] = result.single()["count"]

                # Contar modelos
                result = session.run(f"MATCH (n:{self.schema.NODE_MODEL}) RETURN count(n) as count")
                stats["models"] = result.single()["count"]

                # Contar vistas
                result = session.run(f"MATCH (n:{self.schema.NODE_VIEW}) RETURN count(n) as count")
                stats["views"] = result.single()["count"]

                # Contar campos
                result = session.run(f"MATCH (n:{self.schema.NODE_FIELD}) RETURN count(n) as count")
                stats["fields"] = result.single()["count"]

                return stats
        except Exception as e:
            print(f"Warning: No se pudieron obtener estadísticas: {e}")
            return {
                "modules": 0,
                "models": 0,
                "views": 0,
                "fields": 0,
            }
