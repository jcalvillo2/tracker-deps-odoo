### Story 002 — Extract and Index Odoo Models

**User Story**  
As a data engineer, I want to parse all Python files defining Odoo models so that I can capture their structure and relationships.

**Acceptance Criteria**  
- Detects classes inheriting from `models.Model`.  
- Extracts `_name`, `_inherit`, `_inherits`, `_description`, and field definitions.  
- Distinguishes base models (those defining `_name`) from inherited ones.  
- Outputs a normalized model object.  

**Technical Tasks**  
- Use Python’s `ast` or regex parsing to analyze model files.  
- Identify parent and child relationships.  
- Prepare model nodes for Neo4j ingestion.  

**Example Input/Output**  

**Input:**  
```python
class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = "mail.thread"
```
   
**Output:**

{
  "name": "res.partner",
  "inherits": ["mail.thread"],
  "fields": []
}