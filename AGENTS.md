# Repository rules

| Rule | Enforcement |
| --- | --- |
| A group's crossing, site, and language change only in `classroom/state.py`, through `Group.receive_form` and `Group.move_to_partner_site`. A form that names another site cannot replace the crossing the group carried. | `python3 -B -m unittest tests.test_group_crossing` |
| Only the classroom service process may replace the Mac launcher window or close it. A reopen helper cannot. | `python3 -B -m unittest tests.test_launch_lifetime` calls `LaunchLifetime` in `tools/mac_classroom/LaunchLifetime.swift` |
| Teachers start a Mac checkout with `sh classroom/mac_teacher.sh`. Entry documents do not copy those commands or launch the simulator. | `python3 -B -m unittest tests.test_teacher_startup` |
