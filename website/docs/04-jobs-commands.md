# 05 - Jobs (UI-First Workflow)

Jobs are now designed for **board + button + modal** usage.

## 1) Create a job
- Go to `jobs-board`
- Click **Post Job**
- Choose area
- Choose tier
- Fill modal (title, description, reward)

Result:
- Job is posted to the mapped area channel (`jobs-general/salvage/mining/hauling/event`)
- Escrow is reserved at creation

---

## 2) Accept and run job
- Open the job card
- Click **Accept**

Result:
- Thread is created
- Main card and thread control card are synced

---

## 3) Crew management (non-event jobs)
After accept/claim, use crew UI from either:
- the thread control card **Crew** button, or
- `jobs-board` → **Crew**

Crew UI actions:
- **Add Crew**
- **Remove Crew**
- **View Crew**

Rules:
- Non-event jobs only
- Job must be claimed/completed
- Managed by claimer, Jobs Admin, Finance, or Admin

---

## 4) Complete + confirm payout
- Claimer/admin marks job complete from the job card
- Finance/admin confirms payout from the card

Result:
- Non-event: payout split across claimer + crew
- Event: payout split across attendance snapshot
- Rep and ledger updates applied

---

## 5) Event jobs
Event jobs are RSVP/attendance based (no claim path).
Use the event flow in the Event Jobs page.
