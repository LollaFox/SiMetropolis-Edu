# SiMetropolis Edu · Long Valley classroom

[繁體中文](README_ZH.md)

## Open the classroom on Mac

The launcher requires Python 3.9 or later. Open Terminal in the folder containing this README. For a checkout at `~/Documents/SiMetropolis Edu`, run `cd "$HOME/Documents/SiMetropolis Edu"` first. Start the classroom from that folder.

```sh
sh classroom/mac_teacher.sh
```

The first run needs internet access and installs the classroom. Leave that Terminal window open during the lesson. To reopen the teacher tab, run the same command in a second Terminal window from the same folder. Your class keeps its join code, timer, and group work.

## Open the classroom on Windows

In the project folder, double-click **Open SiMetropolis Edu.cmd** or the existing **start-product.cmd** shortcut. Keep internet access on during first-use setup. If a transfer stops, reconnect and select **Retry**. Keep the launcher running during the lesson. Double-click the shortcut again to reopen the teacher tab.

## From teacher sign-in to the QR page

1. The launcher signs you in and opens **Choose a lesson** at `/teacher`. If you open that path manually while signed out, enter your teacher credential and select **Sign in**. If a class is already running, the teacher tab opens its live controls.
2. Select **A railway across Long Valley**, choose the starting language, and click **Start Lesson**. The 45-minute timer starts immediately.
3. On the live lesson page, select **Launch the QR code page**. A separate projector tab shows the QR code, join link, and short code for groups on the classroom network.

If Edu detects a network problem, the teacher tab shows **Open network settings** and keeps retrying. Join information returns when the computer reconnects, and the original countdown continues.

See the [Long Valley classroom guide](classroom/README.md) for teaching and setup details.

## License

See the [SiMetropolis Decision Sandbox Restricted License](LICENSE) for permitted use and distribution.
