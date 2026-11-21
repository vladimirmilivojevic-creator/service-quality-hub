# IT service processes – a short guide for Plant IT teams

These one-page process descriptions belong to the fictional **Valdora Machinery Group** (five plants, one central IT
provider, several external vendors). They show how the processes are meant to work across all plants, and how
ServiceQualityHub supports and measures them. They follow ITIL 4 practices, written in plain English.

| Process | One sentence | Main KPI |
|---|---|---|
| [Incident management](incident.md) | Restore normal service as fast as possible. | Resolution SLA compliance, MTTR |
| [Service request management](service-request.md) | Deliver standard requests (accounts, devices, restores) in an agreed time. | Resolution SLA compliance |
| [Problem management](problem.md) | Find and remove the root cause of recurring incidents. | Recurring incidents, problems resolved |
| [Change enablement](change.md) | Make changes without breaking production. | Change success rate |
| [Service review](service-review.md) | Check every month, with every provider, whether the agreed service was delivered. | Supplier scorecard, improvement actions on time |

## The same minimum standard at every plant

1. **One service catalogue.** Every ticket is linked to a catalogue service. Only the catalogue defines support hours,
   criticality and SLA targets.
2. **One priority rule.** Priority = impact × urgency (the matrix is on the "How it works" page of the live demo).
   Nobody sets P1 "because it is urgent for me".
3. **One SLA clock.** Support hours in the plant's local time; the clock stops only in status *Pending*
   (waiting for the user), never while waiting for another IT team or a vendor.
4. **"Resolved" means the user confirmed it.** Otherwise the ticket comes back (reopen rate).
5. **Every recurring issue gets a problem record**, every change a risk check, every red KPI an improvement action
   with an owner and a due date.

## Roles used in the RACI tables

| Role | Who |
|---|---|
| Service desk | First contact for users (central service desk or Plant IT) |
| Plant IT | The IT team of each plant (OLA with the Service Quality Manager) |
| Central IT provider | Group IT provider for ERP, PLM, email, identity, backup (OLA) |
| Vendor | External supplier with a contract (WAN, managed print, scanners) |
| Service owner | Accountable for one catalogue service end to end |
| Service Quality Manager (SQM) | Owns the processes, the catalogue, the KPIs and the service reviews |
| Change Advisory Board (CAB) | Assesses normal changes (service owners, Plant IT leads, SQM) |

R = responsible (does the work) · A = accountable (one person, signs off) · C = consulted · I = informed
