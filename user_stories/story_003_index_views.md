### Story 003 — Extract and Index Odoo Views

**User Story**  
As a data engineer, I want to parse XML view files to extract their type, name, and inheritance relationships so that I can link UI dependencies.

**Acceptance Criteria**  
- Detects `<record model="ir.ui.view">`.  
- Extracts `name`, `inherit_id`, and view type (`form`, `tree`, `kanban`, etc.).  
- Associates view with its corresponding model (if defined).  

**Technical Tasks**  
- Parse XML files using an XML parser.  
- Build view graph: base views, inherited views, extensions.  

**Example Input/Output**  

**Input:**  
```xml

<record id="view_partner_form" model="ir.ui.view">
  <field name="name">res.partner.form</field>
  <field name="model">res.partner</field>
  <field name="inherit_id" ref="base.view_partner_form"/>
</record>
```

**Output:**
```json
{
  "id": "view_partner_form",
  "model": "res.partner",
  "inherit_id": "base.view_partner_form",
  "type": "form"
}
```