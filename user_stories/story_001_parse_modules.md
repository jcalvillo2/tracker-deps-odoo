### Story 001 — Parse and Identify Odoo Modules

**User Story**
As a data engineer, I want to extract and identify all Odoo modules from a given source path so that I can process them individually in the ETL pipeline.

**Acceptance Criteria**
- Detects `__manifest__.py` files as module boundaries.
- Reads metadata (name, depends, version, summary, etc.).
- Stores module info in a structured JSON or dictionary.

**Technical Tasks**
- Traverse Odoo directory tree recursively.
- Parse each `__manifest__.py`.
- Build an in-memory representation of modules and dependencies.

**Example Input/Output**

Input:
path = "/odoo/addons"

Output:
[
  {"name": "sale", "depends": ["base", "product"]},
  {"name": "crm", "depends": ["base"]}
]
