#!/usr/bin/env python3
"""
CLI principal para el sistema ETL de análisis de dependencias Odoo.
"""
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from src.discovery import ModuleScanner
from src.parsers import ModelParser, ViewParser
from src.graph import Neo4jLoader
from src.incremental import ChangeDetector, StateManager
from src.query import QueryEngine
from src.visualization import GraphVisualizer

console = Console()


def parse_module(module):
    """
    Parsea un módulo individual (modelos y vistas).
    Diseñado para ejecutarse en paralelo.

    Args:
        module: Objeto Module a parsear

    Returns:
        Tupla (lista_modelos, lista_vistas)
    """
    module_path = Path(module.path)

    # Parsear modelos
    model_parser = ModelParser(module.name)
    models = model_parser.parse_directory(module_path)

    # Parsear vistas
    view_parser = ViewParser(module.name)
    views = view_parser.parse_directory(module_path)

    return ([m.to_dict() for m in models], [v.to_dict() for v in views])


def organize_data_for_loading(modules, all_models, all_views):
    """
    Organiza los datos parseados en estructuras optimizadas para carga.
    Separa nodos de relaciones para cargar en orden óptimo.

    Args:
        modules: Lista de módulos
        all_models: Lista de modelos parseados
        all_views: Lista de vistas parseadas

    Returns:
        Diccionario con datos organizados
    """
    console.print("\n[cyan]Organizando datos para carga optimizada...[/cyan]")

    data = {
        # Nodos primero
        "modules": [m.to_dict() for m in modules],
        "models": [],
        "views": [],
        "fields": [],

        # Relaciones después
        "module_dependencies": [],
        "model_module_rels": [],
        "model_inheritances": [],
        "model_delegations": [],
        "field_model_rels": [],
        "field_references": [],
        "view_module_rels": [],
        "view_model_rels": [],
        "view_inheritances": []
    }

    # Extraer dependencias de módulos
    for module in modules:
        for dep in module.depends:
            data["module_dependencies"].append({
                "from": module.name,
                "to": dep
            })

    # Procesar modelos
    for model in all_models:
        if not model.get("name"):
            continue

        # Calcular model_type
        is_transient = model.get("is_transient", False)
        inherits = model.get("inherits", [])
        model_name = model.get("name")

        if is_transient:
            model_type = "transient"
        elif not model_name:
            model_type = "mixin"
        elif inherits and model_name in inherits:
            model_type = "extension"
        elif inherits and model_name not in inherits:
            model_type = "redefined"
        else:
            model_type = "base"

        # Nodo de modelo (sin relaciones)
        data["models"].append({
            "name": model_name,
            "description": model.get("description", ""),
            "module": model["module"],
            "file_path": model["file_path"],
            "class_name": model["class_name"],
            "model_type": model_type,
            "is_abstract": model.get("is_abstract", False),
            "is_extension": model.get("is_extension", False),
            "is_transient": is_transient
        })

        # Relación módulo→modelo
        data["model_module_rels"].append({
            "model": model["name"],
            "module": model["module"]
        })

        # Herencias
        for parent in model.get("inherits", []):
            data["model_inheritances"].append({
                "child": model["name"],
                "parent": parent
            })

        # Delegaciones
        for parent, field in model.get("inherits_models", {}).items():
            data["model_delegations"].append({
                "child": model["name"],
                "parent": parent,
                "field": field
            })

        # Procesar campos
        for field in model.get("fields", []):
            field_name = field.get("name")
            if not field_name:
                continue

            # Nodo de campo
            data["fields"].append({
                "model_name": model["name"],
                "field_name": field_name,
                "field_type": field.get("field_type", ""),
                "related_model": field.get("related_model"),
                "attributes": field.get("attributes", {})
            })

            # Relación campo→modelo
            data["field_model_rels"].append({
                "field_name": field_name,
                "model_name": model["name"]
            })

            # Referencias a otros modelos
            if field.get("related_model"):
                data["field_references"].append({
                    "field_name": field_name,
                    "model_name": model["name"],
                    "related_model": field["related_model"]
                })

    # Procesar vistas
    for view in all_views:
        if not view.get("xml_id") or not view.get("model"):
            continue

        # Nodo de vista (sin relaciones)
        data["views"].append({
            "xml_id": view["xml_id"],
            "name": view.get("name", ""),
            "model": view["model"],
            "view_type": view.get("view_type", ""),
            "module": view["module"],
            "file_path": view.get("file_path", ""),
            "priority": view.get("priority", 16)
        })

        # Relación módulo→vista
        data["view_module_rels"].append({
            "view_xml_id": view["xml_id"],
            "module": view["module"]
        })

        # Relación vista→modelo
        data["view_model_rels"].append({
            "view_xml_id": view["xml_id"],
            "model": view["model"]
        })

        # Herencias de vistas
        if view.get("inherit_id"):
            data["view_inheritances"].append({
                "child": view["xml_id"],
                "parent": view["inherit_id"]
            })

    # Mostrar estadísticas
    console.print(f"  • {len(data['modules'])} módulos")
    console.print(f"  • {len(data['models'])} modelos")
    console.print(f"  • {len(data['views'])} vistas")
    console.print(f"  • {len(data['fields'])} campos")
    console.print(f"  • {len(data['module_dependencies'])} dependencias de módulos")
    console.print(f"  • {len(data['model_inheritances'])} herencias de modelos")
    console.print(f"  • {len(data['field_references'])} referencias entre campos")

    return data


@click.group()
def cli():
    """Sistema ETL para análisis de dependencias de Odoo."""
    pass


@cli.command()
@click.option(
    "--source",
    "-s",
    type=click.Path(exists=True),
    help="Ruta al código fuente de Odoo",
)
@click.option("--full", is_flag=True, help="Forzar carga completa (ignorar incremental)")
@click.option("--clear", is_flag=True, help="Limpiar el grafo antes de cargar")
def load(source, full, clear):
    """Carga el código fuente de Odoo en Neo4j."""
    source_path = Path(source or Config.ODOO_SOURCE_PATH)

    if not source_path.exists():
        console.print(f"[red]Error: La ruta {source_path} no existe[/red]")
        return

    console.print(f"[bold blue]Analizando código fuente de Odoo en:[/bold blue] {source_path}")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # 1. Descubrir módulos
            task = progress.add_task("Descubriendo módulos...", total=None)
            scanner = ModuleScanner(source_path)
            modules = scanner.scan()
            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] {len(modules)} módulos encontrados")

            # 2. Determinar estrategia incremental
            if not full:
                task = progress.add_task("Detectando cambios...", total=None)
                state_manager = StateManager()
                detector = ChangeDetector(state_manager)
                strategy = detector.get_incremental_strategy(
                    [m.to_dict() for m in modules]
                )
                progress.update(task, completed=True)

                console.print(f"[yellow]Estrategia:[/yellow] {strategy['reason']}")

                if not strategy["full_reload"]:
                    modules_to_process = [
                        m
                        for m in modules
                        if m.name in [cm["name"] for cm in strategy["changed_modules"]]
                    ]
                    console.print(
                        f"[cyan]Procesando {len(modules_to_process)} módulos modificados[/cyan]"
                    )
                else:
                    modules_to_process = modules
            else:
                modules_to_process = modules
                state_manager = StateManager()

            # 3. Parsear modelos y vistas (en paralelo)
            task = progress.add_task("Parseando modelos y vistas...", total=None)
            all_models = []
            all_views = []

            # Usar ThreadPoolExecutor para parsing paralelo
            with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
                # Enviar todos los módulos para procesamiento paralelo
                future_to_module = {
                    executor.submit(parse_module, module): module
                    for module in modules_to_process
                }

                # Recolectar resultados a medida que se completan
                for future in as_completed(future_to_module):
                    try:
                        models, views = future.result()
                        all_models.extend(models)
                        all_views.extend(views)
                    except Exception as e:
                        module = future_to_module[future]
                        console.print(
                            f"[red]Error parseando módulo {module.name}: {e}[/red]"
                        )

            progress.update(task, completed=True)
            console.print(
                f"[green]✓[/green] {len(all_models)} modelos y {len(all_views)} vistas parseados"
            )

            # 3.5. Organizar datos (patrón ETL)
            organized_data = organize_data_for_loading(modules, all_models, all_views)

        # 4. Cargar en Neo4j (fuera del Progress context para usar su propia lógica de progreso)
        with Neo4jLoader() as loader:
            # Configurar esquema
            loader.setup_schema()

            # Limpiar si se solicita
            if clear or full:
                loader.clear_graph()
                console.print("[yellow]Grafo limpiado[/yellow]")

            # Cargar datos organizados
            loader.load_organized_data(organized_data)

            # Obtener estadísticas
            stats = loader.get_stats()

        # 5. Actualizar estado
        for module in modules_to_process:
            state_manager.mark_module_processed(Path(module.path))
        state_manager.save_state()

        # Mostrar resumen
        console.print("\n[bold green]✓ Carga completada exitosamente[/bold green]\n")

        table = Table(title="Estadísticas del Grafo")
        table.add_column("Tipo", style="cyan")
        table.add_column("Cantidad", style="magenta", justify="right")

        table.add_row("Módulos", str(stats["modules"]))
        table.add_row("Modelos", str(stats["models"]))
        table.add_row("Vistas", str(stats["views"]))
        table.add_row("Campos", str(stats["fields"]))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


@cli.group()
def query():
    """Consultas sobre el grafo de dependencias."""
    pass


@query.command("model-children")
@click.argument("model_name")
def query_model_children(model_name):
    """Obtiene los modelos que heredan de un modelo."""
    with QueryEngine() as engine:
        results = engine.get_model_children(model_name)

        if not results:
            console.print(f"[yellow]No se encontraron hijos para {model_name}[/yellow]")
            return

        table = Table(title=f"Modelos que heredan de '{model_name}'")
        table.add_column("Modelo", style="cyan")
        table.add_column("Módulo", style="magenta")
        table.add_column("Tipo", style="green")

        for result in results:
            table.add_row(result["name"], result["module"], result["model_type"])

        console.print(table)


@query.command("model-parents")
@click.argument("model_name")
def query_model_parents(model_name):
    """Obtiene los modelos padre de un modelo."""
    with QueryEngine() as engine:
        results = engine.get_model_parents(model_name)

        if not results:
            console.print(f"[yellow]No se encontraron padres para {model_name}[/yellow]")
            return

        table = Table(title=f"Modelos padre de '{model_name}'")
        table.add_column("Modelo", style="cyan")
        table.add_column("Módulo", style="magenta")
        table.add_column("Tipo", style="green")

        for result in results:
            table.add_row(result["name"], result["module"], result["model_type"])

        console.print(table)


@query.command("model-views")
@click.argument("model_name")
def query_model_views(model_name):
    """Obtiene las vistas de un modelo."""
    with QueryEngine() as engine:
        results = engine.get_views_for_model(model_name)

        if not results:
            console.print(f"[yellow]No se encontraron vistas para {model_name}[/yellow]")
            return

        table = Table(title=f"Vistas del modelo '{model_name}'")
        table.add_column("XML ID", style="cyan")
        table.add_column("Nombre", style="magenta")
        table.add_column("Tipo", style="green")
        table.add_column("Módulo", style="yellow")

        for result in results:
            table.add_row(
                result["xml_id"], result["name"], result["view_type"], result["module"]
            )

        console.print(table)


@query.command("model-relations")
@click.argument("model_name")
def query_model_relations(model_name):
    """Obtiene las relaciones de campos de un modelo."""
    with QueryEngine() as engine:
        results = engine.get_model_relations(model_name)

        if not results:
            console.print(
                f"[yellow]No se encontraron relaciones para {model_name}[/yellow]"
            )
            return

        table = Table(title=f"Relaciones del modelo '{model_name}'")
        table.add_column("Campo", style="cyan")
        table.add_column("Tipo", style="magenta")
        table.add_column("Modelo Destino", style="green")

        for result in results:
            table.add_row(
                result["field_name"], result["field_type"], result["target_model"]
            )

        console.print(table)


@query.command("model-impact")
@click.argument("model_name")
def query_model_impact(model_name):
    """Analiza el impacto de un modelo."""
    with QueryEngine() as engine:
        result = engine.get_model_impact(model_name)

        if not result:
            console.print(f"[yellow]No se encontró el modelo {model_name}[/yellow]")
            return

        table = Table(title=f"Análisis de Impacto: '{model_name}'")
        table.add_column("Métrica", style="cyan")
        table.add_column("Cantidad", style="magenta", justify="right")

        table.add_row("Modelos hijos", str(result["children_count"]))
        table.add_row("Vistas asociadas", str(result["views_count"]))
        table.add_row("Modelos relacionados", str(result["related_models_count"]))

        console.print(table)


@query.command("search")
@click.argument("search_term")
def query_search(search_term):
    """Busca modelos por nombre."""
    with QueryEngine() as engine:
        results = engine.search_models(search_term)

        if not results:
            console.print(
                f"[yellow]No se encontraron modelos con '{search_term}'[/yellow]"
            )
            return

        table = Table(title=f"Modelos que contienen '{search_term}'")
        table.add_column("Modelo", style="cyan")
        table.add_column("Módulo", style="magenta")
        table.add_column("Descripción", style="green")

        for result in results:
            table.add_row(
                result["name"], result["module"], result["description"] or "-"
            )

        console.print(table)


@cli.group()
def visualize():
    """Visualización del grafo."""
    pass


@visualize.command("model-hierarchy")
@click.argument("model_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="model_hierarchy.html",
    help="Archivo de salida",
)
@click.option("--depth", "-d", default=3, help="Profundidad de la jerarquía")
def viz_model_hierarchy(model_name, output, depth):
    """Visualiza la jerarquía de herencia de un modelo."""
    with GraphVisualizer() as viz:
        output_path = Path(output)
        viz.visualize_model_hierarchy(model_name, output_path, depth)
        console.print(
            f"[green]✓ Visualización creada:[/green] {output_path.absolute()}"
        )


@visualize.command("model-relations")
@click.argument("model_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="model_relations.html",
    help="Archivo de salida",
)
def viz_model_relations(model_name, output):
    """Visualiza las relaciones de campos de un modelo."""
    with GraphVisualizer() as viz:
        output_path = Path(output)
        viz.visualize_model_relations(model_name, output_path)
        console.print(
            f"[green]✓ Visualización creada:[/green] {output_path.absolute()}"
        )


@visualize.command("module-deps")
@click.option("--module", "-m", help="Módulo específico (opcional)")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="module_deps.html",
    help="Archivo de salida",
)
def viz_module_deps(module, output):
    """Visualiza las dependencias entre módulos."""
    with GraphVisualizer() as viz:
        output_path = Path(output)
        viz.visualize_module_dependencies(module, output_path)
        console.print(
            f"[green]✓ Visualización creada:[/green] {output_path.absolute()}"
        )


@cli.command()
def stats():
    """Muestra estadísticas del grafo."""
    with Neo4jLoader() as loader:
        stats = loader.get_stats()

    table = Table(title="Estadísticas del Grafo de Dependencias")
    table.add_column("Tipo de Nodo", style="cyan")
    table.add_column("Cantidad", style="magenta", justify="right")

    table.add_row("Módulos", str(stats["modules"]))
    table.add_row("Modelos", str(stats["models"]))
    table.add_row("Vistas", str(stats["views"]))
    table.add_row("Campos", str(stats["fields"]))

    console.print(table)


@cli.command()
def clear():
    """Limpia el grafo y el estado."""
    if click.confirm("¿Deseas limpiar completamente el grafo y el estado?"):
        with Neo4jLoader() as loader:
            loader.clear_graph()

        state_manager = StateManager()
        state_manager.clear_state()

        console.print("[green]✓ Grafo y estado limpiados[/green]")


if __name__ == "__main__":
    cli()
