# Repository rules

| Rule                                                                                                                                                                                                                     | Enforcement                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| A group's crossing, site, and language change only in `classroom/state.py`, through `Group.receive_form` and `Group.move_to_partner_site`. A form that names another site cannot replace the crossing the group carried. | `python3 -B -m unittest tests.test_group_crossing`                                                                       |
| Only the classroom service process may replace the Mac launcher window or close it. A reopen helper cannot.                                                                                                              | `python3 -B -m unittest tests.test_launch_lifetime` calls `LaunchLifetime` in `tools/mac_classroom/LaunchLifetime.swift` |
| Teachers start a Mac checkout with `sh classroom/mac_teacher.sh`. Entry documents do not copy those commands or launch the simulator.                                                                                    | `python3 -B -m unittest tests.test_teacher_startup`                                                                      |

## Page copy limit

Use at most three visible text blocks in the main content of each page. Count each eyebrow (a short label above a heading), heading, instruction, and descriptive paragraph separately, even when they share a container. Exclude button labels, primary labels of selectable items. Count descriptive copy and status label inside a selectable item toward the page total.

## Page button limit

Display at most three action buttons per page. Exclude collection items used solely for navigation or selection. Count any separate action buttons within those items towards the page total.

## Per-page color palette

Limit each page’s UI palette to three colors, counting only colors applied to UI elements outside the product icon and imagery.
