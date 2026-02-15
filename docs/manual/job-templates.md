# Job Templates

## Manage templates
- `/jobtemplates add` -> modal create
- `/jobtemplates update name:<template>` -> modal update
- `/jobtemplates list`
- `/jobtemplates view name:<template>`
- `/jobtemplates clone source_name new_name`
- `/jobtemplates disable name:<template>`
- `/jobtemplates enable name:<template>`
- `/jobtemplates delete name:<template>`

## Use a template
- `/jobs post template:<name>`

If template category is `event`, posting is restricted to:
- `EVENT_HANDLER_ROLE_ID` role
- or admin

Templates are persisted in SQLite table: `job_templates`.
