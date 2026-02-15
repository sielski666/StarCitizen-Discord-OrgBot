# 05 - Job Template Commands

Templates store defaults for repeatable jobs.

## `/jobtemplates add`
**Who:** admin

**How to use:**
- Opens modal.
- Fill name, title, description, reward range, tier/category.

**What it does:**
- Creates new template in database.

---

## `/jobtemplates update name:<template>`
**Who:** admin

**How to use:**
- Opens prefilled modal for existing template.

**What it does:**
- Updates template fields.

---

## `/jobtemplates clone source_name:<src> new_name:<dst>`
**Who:** admin

Copies one template to a new name.

## `/jobtemplates list [include_inactive:true|false]`
Lists templates with reward/tier/category and active state.

## `/jobtemplates view name:<template>`
Shows full details for one template.

## `/jobtemplates disable name:<template>`
Marks template inactive (cannot be used for posting).

## `/jobtemplates enable name:<template>`
Re-enables template.

## `/jobtemplates delete name:<template>`
Deletes template from DB.

---

## Notes
- Event templates (`category=event`) can only be posted by Event Handler/Admin.
- Templates persist in table `job_templates`.
