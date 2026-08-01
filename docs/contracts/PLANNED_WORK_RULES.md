# Planned work rules

Status: factual product contract; implementation is outside PIVOT-001.

One manually entered planned work item produces:

1. one overall-period row for the new morning report;
2. optionally, a working-day daytime expansion for the commercial dispatch
   centre.

Expansion is allowed only when both conditions are true:

- power is reduced / `P ремонт` is filled;
- structured execution mode is
  `С вводом в работу на ночь и в выходные дни`.

Expansion rules:

- Saturday and Sunday are excluded;
- equipment is considered returned to service at night;
- only daytime intervals of working days are emitted;
- work without generation loss is not expanded;
- for work without generation loss, `P уставка`, `P ремонт` and
  `P располагаемая` remain empty.

The execution mode must be stored as a structured field. Free-text recognition
may be an import aid, but cannot be the only business-rule trigger.
