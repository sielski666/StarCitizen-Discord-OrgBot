# Job Templates

Templates standardize job posts and reduce mistakes.

## Create/update templates
- `/jobtemplates add` -> opens modal for new template
- `/jobtemplates update name:<template>` -> opens modal prefilled from existing template

Modal fields:
- Template name
- Default job title
- Default description
- Reward range (min,max)
- Tier/category (tier,category)

## Manage templates
- `/jobtemplates list`
- `/jobtemplates view name:<template>`
- `/jobtemplates clone source_name:<src> new_name:<dst>`
- `/jobtemplates disable name:<template>`
- `/jobtemplates enable name:<template>`
- `/jobtemplates delete name:<template>`

## Using templates
- `/jobs post template:<name>`

If template category is `event`, posting is restricted to:
- `Event Handler` role (`EVENT_HANDLER_ROLE_ID`)
- or Admin

## Storage
Templates persist in DB table: `job_templates`.
