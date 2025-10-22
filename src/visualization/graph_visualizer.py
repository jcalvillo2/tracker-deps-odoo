"""
Visualizador de grafos usando pyvis y networkx.
"""
from pathlib import Path
from typing import List, Dict, Optional
import networkx as nx
from pyvis.network import Network
from neo4j import GraphDatabase
from config import Config
from src.graph.schema import GraphSchema


class GraphVisualizer:
    """Visualizador de grafos de dependencias Odoo."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """
        Inicializa el visualizador.

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

    def visualize_model_hierarchy(
        self, model_name: str, output_file: Path, depth: int = 3
    ):
        """
        Visualiza la jerarquía de herencia de un modelo.

        Args:
            model_name: Nombre del modelo
            output_file: Ruta del archivo HTML de salida
            depth: Profundidad de la jerarquía
        """
        # Obtener datos del grafo
        query = f"""
        MATCH (root:{self.schema.NODE_MODEL} {{name: $model_name}})
        OPTIONAL MATCH path1 = (child:{self.schema.NODE_MODEL})-[:{self.schema.REL_MODEL_INHERITS}*..{depth}]->(root)
        OPTIONAL MATCH path2 = (root)-[:{self.schema.REL_MODEL_INHERITS}*..{depth}]->(parent:{self.schema.NODE_MODEL})
        WITH root, collect(path1) + collect(path2) as paths
        UNWIND paths as path
        UNWIND relationships(path) as rel
        WITH root, startNode(rel) as source, endNode(rel) as target
        RETURN DISTINCT
            root.name as root_name,
            source.name as source,
            target.name as target,
            source.module as source_module,
            target.module as target_module
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            records = [dict(record) for record in result]

        if not records:
            print(f"No se encontró el modelo {model_name}")
            return

        # Crear grafo
        net = Network(height="800px", width="100%", directed=True, notebook=False)
        net.toggle_physics(True)

        # Configurar opciones visuales
        net.set_options(
            """
        {
            "nodes": {
                "font": {"size": 16}
            },
            "edges": {
                "arrows": {"to": {"enabled": true}},
                "smooth": {"type": "continuous"}
            },
            "physics": {
                "enabled": true,
                "stabilization": {"iterations": 100}
            }
        }
        """
        )

        # Agregar nodos y relaciones
        added_nodes = set()

        for record in records:
            source = record["source"]
            target = record["target"]
            root_name = record["root_name"]

            # Determinar colores
            def get_color(node_name):
                if node_name == root_name:
                    return "#ff6b6b"  # Rojo para nodo raíz
                return "#4dabf7"  # Azul para otros

            # Agregar nodos
            if source not in added_nodes:
                net.add_node(
                    source,
                    label=f"{source}\n({record['source_module']})",
                    color=get_color(source),
                    title=f"Modelo: {source}\nMódulo: {record['source_module']}",
                )
                added_nodes.add(source)

            if target not in added_nodes:
                net.add_node(
                    target,
                    label=f"{target}\n({record['target_module']})",
                    color=get_color(target),
                    title=f"Modelo: {target}\nMódulo: {record['target_module']}",
                )
                added_nodes.add(target)

            # Agregar relación
            net.add_edge(source, target, title="inherits")

        # Guardar
        net.save_graph(str(output_file))
        print(f"Visualización guardada en: {output_file}")

    def visualize_model_relations(
        self, model_name: str, output_file: Path, depth: int = 2
    ):
        """
        Visualiza las relaciones de campos de un modelo.

        Args:
            model_name: Nombre del modelo
            output_file: Ruta del archivo HTML de salida
            depth: Profundidad de relaciones
        """
        query = f"""
        MATCH (m:{self.schema.NODE_MODEL} {{name: $model_name}})-[:{self.schema.REL_MODEL_HAS_FIELD}]->(f:{self.schema.NODE_FIELD})
        MATCH (f)-[:{self.schema.REL_FIELD_RELATES_TO}]->(target:{self.schema.NODE_MODEL})
        RETURN m.name as source, f.name as field_name, f.field_type as field_type, target.name as target
        """

        with self.driver.session() as session:
            result = session.run(query, model_name=model_name)
            records = [dict(record) for record in result]

        if not records:
            print(f"No se encontraron relaciones para {model_name}")
            return

        # Crear grafo
        net = Network(height="800px", width="100%", directed=True)
        net.toggle_physics(True)

        added_nodes = set()

        for record in records:
            source = record["source"]
            target = record["target"]
            field_name = record["field_name"]
            field_type = record["field_type"]

            # Agregar nodos
            if source not in added_nodes:
                net.add_node(source, label=source, color="#ff6b6b")
                added_nodes.add(source)

            if target not in added_nodes:
                net.add_node(target, label=target, color="#4dabf7")
                added_nodes.add(target)

            # Agregar relación con etiqueta del campo
            net.add_edge(
                source,
                target,
                label=f"{field_name}\n({field_type})",
                title=f"Campo: {field_name}\nTipo: {field_type}",
            )

        net.save_graph(str(output_file))
        print(f"Visualización guardada en: {output_file}")

    def visualize_module_dependencies(
        self, module_name: str = None, output_file: Path = None
    ):
        """
        Visualiza las dependencias entre módulos.

        Args:
            module_name: Nombre del módulo (None para todos)
            output_file: Ruta del archivo HTML de salida
        """
        if module_name:
            query = f"""
            MATCH (m:{self.schema.NODE_MODULE} {{name: $module_name}})
            OPTIONAL MATCH path = (m)-[:{self.schema.REL_MODULE_DEPENDS}*..2]->(dep:{self.schema.NODE_MODULE})
            WITH m, collect(path) as paths
            UNWIND paths as path
            UNWIND relationships(path) as rel
            WITH startNode(rel) as source, endNode(rel) as target
            RETURN DISTINCT source.name as source, target.name as target
            """
            params = {"module_name": module_name}
        else:
            query = f"""
            MATCH (m:{self.schema.NODE_MODULE})-[:{self.schema.REL_MODULE_DEPENDS}]->(dep:{self.schema.NODE_MODULE})
            RETURN m.name as source, dep.name as target
            LIMIT 200
            """
            params = {}

        with self.driver.session() as session:
            result = session.run(query, **params)
            records = [dict(record) for record in result]

        if not records:
            print("No se encontraron dependencias")
            return

        # Crear grafo
        net = Network(height="800px", width="100%", directed=True)
        net.toggle_physics(True)

        added_nodes = set()

        for record in records:
            source = record["source"]
            target = record["target"]

            # Determinar color
            highlight_color = "#ff6b6b" if source == module_name else "#4dabf7"

            if source not in added_nodes:
                net.add_node(source, label=source, color=highlight_color)
                added_nodes.add(source)

            if target not in added_nodes:
                net.add_node(target, label=target, color="#4dabf7")
                added_nodes.add(target)

            net.add_edge(source, target)

        output = output_file or Path("module_dependencies.html")
        net.save_graph(str(output))
        print(f"Visualización guardada en: {output}")

    def export_to_graphml(self, output_file: Path):
        """
        Exporta el grafo completo a formato GraphML.

        Args:
            output_file: Ruta del archivo de salida
        """
        # Obtener todos los nodos y relaciones
        query = """
        MATCH (n)-[r]->(m)
        RETURN
            id(n) as source_id,
            labels(n)[0] as source_type,
            n.name as source_name,
            type(r) as rel_type,
            id(m) as target_id,
            labels(m)[0] as target_type,
            m.name as target_name
        """

        with self.driver.session() as session:
            result = session.run(query)
            records = [dict(record) for record in result]

        # Crear grafo NetworkX
        G = nx.DiGraph()

        for record in records:
            source = f"{record['source_type']}:{record['source_name']}"
            target = f"{record['target_type']}:{record['target_name']}"

            G.add_node(source, type=record["source_type"], name=record["source_name"])
            G.add_node(target, type=record["target_type"], name=record["target_name"])
            G.add_edge(source, target, relationship=record["rel_type"])

        # Exportar
        nx.write_graphml(G, output_file)
        print(f"Grafo exportado a GraphML: {output_file}")
