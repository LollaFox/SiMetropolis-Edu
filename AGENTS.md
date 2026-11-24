# Repository rules

| Rule | Enforcement |
| --- | --- |
| A group's crossing, site, and language change only in `classroom/state.py`, through `Group.receive_form` and `Group.move_to_partner_site`. A form that names another site cannot replace the crossing the group carried. | `python3 -B -m unittest tests.test_group_crossing` |
