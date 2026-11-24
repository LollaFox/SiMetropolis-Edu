# Long Valley classroom

Follow the [Mac Terminal or Windows shortcut instructions](../README.md) to open the classroom from the project folder.

The default browser opens lesson preparation. Select **A railway across Long Valley**, choose the starting language, then click **Start Lesson** when you are ready. On the classroom network, select **Launch the QR code page** to show groups the QR code, link, and short code. Keep the launcher window open while using the classroom.

If Edu loses the classroom network or you start while disconnected, the timer keeps running. Select **Open network settings** if you need to reconnect the computer. Edu retries automatically and restores the join information for the same class when it finds a usable address.

If a returning group scans the restored QR and sees **Choose your starting site**, open **Help a group rejoin** in the private teacher tab. Select the site where the group **started**, even after **Pass the City**, and choose **Get group rejoin code**. Give the code privately to that group. On its device, the group enters the code and selects **Rejoin my group** to reopen its current site with its recorded crossing and chosen language. Each code works once. If the group needs another, select its starting site again to see the current code.

If you close the teacher tab during class, double-click **Open SiMetropolis Edu** again from the same installation. Your class reopens with the original join code and countdown. Groups can keep working in their existing tabs.

If your sign-in link expires while you choose a browser profile, continue in the new teacher tab. If no tab opens, double-click **Open SiMetropolis Edu** again.

### Prepare a local checkout

The shortcuts can use a Python 3.9 or newer virtual environment named `.venv` beside the launchers. Windows sets up a private runtime in `runtime/windows` when it needs one. To prepare a checkout for testing with your own Python, run the commands for your platform from the repository root.

Mac:

```sh
sh classroom/mac_teacher.sh setup
```

Windows:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r classroom\requirements.txt
```

### Build the Windows download

Run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/build-windows-download.ps1` from the repository root. The release asset is `dist/SiMetropolis-Edu-Windows.zip`. It contains the classroom and its launcher. The launcher downloads the embeddable Python archive and pure Python wheels pinned in `tools/windows-classroom-components.json`. Update those wheel pins when changing the classroom dependencies.

### Manual server setup

To run the server and sign in manually, use these commands from the repository root with Python 3.9 or newer.

```sh
python3 -m venv /tmp/long-valley-venv
source /tmp/long-valley-venv/bin/activate
python -m pip install -r classroom/requirements.txt
python -B -m classroom issue-teacher-credential
python -B -m classroom serve
```

Save the printed teacher credential privately. Open [the teacher view](http://127.0.0.1:8899/teacher), sign in, and select **A railway across Long Valley**. Choose the opening language, click **Start Lesson**, open **Launch the QR code page** in the same signed-in browser, and show that tab on the projector. Two neighbouring groups can use the displayed link, QR code, or short code to take one starting site each. Each group shares one device and can switch languages after choosing its site.

Groups choose an alignment, crossing type, and construction access route, then select **Test crossing**. The spring map compares the same site with and without the proposed works. Select a striped area on the map to see which work overlaps modelled nesting habitat there. Keyboard users can tab to the area and press Enter. **Possible disturbance** lists all findings for the crossing.

Groups can switch language or compare views while editing a design. Their selections stay in the controls until they test or reset the crossing. **Replay crossing** reruns the last tested design. **Reset crossing** restores the opening design and map at the assigned site.

Groups select **Share comparison** to send both maps from the tested crossing to the teacher. On the projection tab, open **Shared comparisons** and choose a result to show the two maps together. Groups can keep experimenting while the teacher displays their original comparison.

Each group can select **Save for swap** to keep the crossing it wants to try at the other site. Once both groups have joined, the teacher can select **Pass the City** to move both groups to their partner sites. The new maps open on each group’s own saved crossing. Groups that skipped saving take their last tested crossing. At the partner site, groups can immediately revise, replay, or reset.

Connected group screens switch as soon as they receive the teacher’s swap. If a device loses its connection or resumes from the background while showing its starting site, it hides that map until the classroom confirms the current site.

The 45-minute countdown starts when you select **Start Lesson**. **End class** closes it early, and the same credential opens the next class. Credential hashes are stored in `classroom/.data/teachers`. A server restart closes the current class. For a different storage location, pass the same `--data-dir` before both subcommands.

## Group devices

The shortcut and the default `serve` command listen on local IPv4 interfaces. The launcher opens the private teacher view on the teacher’s computer. The projection uses a connected Wi-Fi or Ethernet address so groups on the same network can join. The classroom network must allow connections between devices.

For testing on one device, use `serve --host 127.0.0.1`. To specify a fixed address, use `--host` and `--public-url` together, then open the teacher view through the public URL. For a server behind an HTTPS reverse proxy, set `--public-url` to the HTTPS origin.

```sh
python -B -m classroom serve --host 192.168.1.10 --public-url http://192.168.1.10:8899
```

## Browser verification

Install Playwright and jsQR in an external test directory. Set `PLAYWRIGHT_PATH` and `JSQR_PATH` to their installed module paths if Node cannot resolve them from the repository. Playwright uses its installed Chromium by default. Set `CHROME_PATH` to use an installed Chrome executable.

```sh
node --test tools/check_long_valley.mjs
```

The connected-class tests start the prepared launcher and use separate browser sessions on the same computer to join through its LAN address. They cover both opening languages, all three join methods and teacher ownership. The timer test checks that reloading the teacher view preserves the original deadline. Run `python -B -m unittest discover -s tests -p test_classroom_network.py` for adapter-selection checks.

To verify a classroom network, open the shortcut on the teacher’s computer and join from a second device on the same Wi-Fi or Ethernet. In an English class, follow the projected link and choose Site A. Start another class in 繁體中文, scan the QR and choose 場地 A, then use a fresh browser session on the student device to enter the short code and choose 場地 B.

On Mac and Windows, verify recovery both before starting and during a lesson. Disconnect Wi-Fi and Ethernet, check that the timer keeps running and the join information is hidden, then use **Open network settings** to reconnect. Keep the teacher and projection tabs open. Check that the notice clears, the original class code reappears, and the second device can join with the restored QR or link. To check a change of address during a lesson, have both groups save different crossings before disconnecting. After reconnecting, have each group scan the restored QR and rejoin with its individual code. Check both crossings and assigned sites.

The launcher checks open the private sign-in link in Chromium, exercise language selection before class, and verify that a second browser cannot reuse the link.

The launcher checks use Chromium to reopen a live class while a group keeps its tested crossing. They also cover separate installations used by the same teacher, a Mac checkout with a read-only classroom directory, and a delayed browser profile selection that overlaps another launch.

On a Windows desktop with internet access, run the following in PowerShell to check first-use setup. Set `WINDOWS_DOWNLOAD_ZIP` to the downloaded ZIP to test that archive. The test extracts the archive, interrupts the Python transfer, selects **Retry** in the setup dialog, and opens the private teacher page. It then reopens the same package with component downloads blocked. On a connected LAN, it starts a class, tests a crossing, and reopens the teacher tab to check the code, deadline, and crossing.

```powershell
$env:WINDOWS_DOWNLOAD_TEST = '1'
node --test --test-name-pattern="Windows download" tools/check_long_valley.mjs
```

The prepared-shortcut checks on Mac and Windows use a temporary virtual environment. To run those checks offline, download the wheels beforehand with `python -m pip download -r classroom/requirements.txt -d wheels`. Set `PIP_NO_INDEX=1` and set `PIP_FIND_LINKS` to the wheel directory's file URL, for example `file:///C:/classroom%20tests/wheels`.

The spring investigation checks cover alignment changes, bridge supports and tunnel entrances drawn on the map, and inspection of overlap evidence by pointer and keyboard. They also exercise the paired sites, the no-works comparison, replay, reset, and language switching with a design still being edited.

The sharing checks verify in both languages that a teacher can project the original maps and evidence after the group changes its crossing, replays, and resets. They also verify that a new share leaves the selected projection in place and that comparisons are private to the class teacher.

## Building and verifying the Mac download

Use macOS with Xcode selected and Python 3 with pip. To create the ZIP for local testing, run `python3 tools/build_mac_classroom.py /tmp/SiMetropolis-Edu-Mac.zip`. The app includes both Mac architectures and the classroom’s Python dependencies. It downloads a pinned [standalone Python runtime](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110) for the current architecture, verifies its SHA-256, and keeps it in the teacher’s Application Support folder.

Pass `--signing-identity "Developer ID Application: …"` and `--notary-profile PROFILE` together to build the distribution ZIP. The script signs the app, submits it to Apple, and packages it with the stapled ticket. It extracts the final ZIP and checks the ticket, signature, and Gatekeeper assessment. Use this signed and notarized archive for distribution. See [Apple's distribution testing guidance](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).

Run `python3 -B -m unittest discover -s tests -p test_mac_classroom_package.py` to build and inspect the extracted package. Set `SIMETROPOLIS_MAC_TEST_ZIP` to the downloaded distribution ZIP to check Gatekeeper and the stapled ticket on the unmodified app. On a logged-in Mac, set `SIMETROPOLIS_MAC_TEST_ARCHIVE` to the native tarball listed in `tools/mac_classroom/runtime.json`. The test opens the app through Launch Services, signs in to lesson preparation, and reopens a running class with the download server offline. Set `SIMETROPOLIS_MAC_TEST_RETRY=1` on a runner with macOS Accessibility access to interrupt the first transfer and press **Retry** in the launcher.

## Verify the teacher downloads

The platform builds produce `SiMetropolis-Edu-Mac.zip` and `SiMetropolis-Edu-Windows.zip`.

1. On a clean Mac and a clean Windows computer, download the distribution ZIP for that platform when available, extract it, and double-click **Open SiMetropolis Edu**. Check setup progress, interrupt the first download, and select **Retry** after reconnecting. When setup finishes, lesson preparation opens privately.
2. On a working classroom network, start an English class on one platform and a Traditional Chinese class on the other. Check that projection is available and the teacher sees no network notice. Use a separate device on that network to join by link in one class and by QR and short code in the other. From the group device, check that the teacher view and projection require teacher access.
3. Run a separate recovery check on each platform. Start disconnected and verify the teacher sees the notice and the original countdown starts. Reconnect and join from the second device. Then disconnect from an already connected class, confirm the notice appears and joining is withheld, and reconnect. Check joining returns without refreshing and the original timer continues.
4. From the student device, test a crossing. Close the teacher tab while leaving the launcher running, then double-click the extracted app or shortcut again. Compare the code and countdown and replay the tested crossing on the student device.
