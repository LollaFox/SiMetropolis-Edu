# Long Valley classroom

On macOS 12 or later, extract `SiMetropolis-Edu-Mac.zip` and double-click **Open SiMetropolis Edu**. The first launch downloads about 24 MB. If the download stops, check your connection and select **Retry**. After setup, you can open lesson preparation while disconnected.

On Windows, extract `SiMetropolis-Edu-Windows.zip` to a local folder and double-click **Open SiMetropolis Edu**. Keep the computer connected to the internet for first-use setup. The launcher shows download progress and offers **Retry** if a download is interrupted. After setup, you can open the same copy while disconnected.

On a prepared Mac checkout, double-click **Open SiMetropolis Edu** (`.command`).

The default browser opens lesson preparation. Choose English or 繁體中文, then click **Start class** when you are ready. On the classroom network, select **Project join information** to show groups the QR code, link, and short code. Keep the launcher window open while using the classroom.

If you spend more than two minutes choosing a browser profile, the launcher opens a fresh sign-in link for the same classroom. Continue in the new teacher tab.

### Prepare a local checkout

The shortcuts can use a Python 3.9 or newer virtual environment named `.venv` beside the launchers. Windows sets up a private runtime in `runtime/windows` when it needs one. To prepare a checkout for testing with your own Python, run the commands for your platform from the repository root.

Mac:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r classroom/requirements.txt
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

Save the printed teacher credential privately. Open [the teacher view](http://127.0.0.1:8899/teacher), sign in, and choose the opening language. Start a class, open **Project join information** in the same signed-in browser, and show that tab on the projector. Two neighbouring groups can use the displayed link, QR code, or short code to take one starting site each. Each group shares one device and can switch languages after choosing its site.

Groups choose an alignment, crossing type, and construction access route, then select **Test crossing**. The spring map compares the same site with and without the proposed works. Select a striped area on the map to see which work overlaps modelled nesting habitat there. Keyboard users can tab to the area and press Enter. **Possible disturbance** lists all findings for the crossing.

Groups can switch language or compare views while editing a design. Their selections stay in the controls until they test or reset the crossing. **Replay crossing** reruns the last tested design. **Reset crossing** restores the opening design and map at the assigned site.

Groups select **Share comparison** to send both maps from the tested crossing to the teacher. On the projection tab, open **Shared comparisons** and choose a result to show the two maps together. Groups can keep experimenting while the teacher displays their original comparison.

Each group can select **Save for swap** to keep the crossing it wants to try at the other site. Once both groups have joined, the teacher can select **Pass the City** to move both groups to their partner sites. The new maps open on each group’s own saved crossing. Groups that skipped saving take their last tested crossing. At the partner site, groups can immediately revise, replay, or reset.

Connected group screens switch as soon as they receive the teacher’s swap. If a device loses its connection or resumes from the background while showing its starting site, it hides that map until the classroom confirms the current site.

The 45-minute countdown starts when you select **Start class**. **End class** closes it early, and the same credential opens the next class. Credential hashes are stored in `classroom/.data/teachers`. A server restart closes the current class. For a different storage location, pass the same `--data-dir` before both subcommands.

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

The launcher checks open the private sign-in link in Chromium, exercise language selection before class, and verify that a second browser cannot reuse the link.

On a Windows desktop with internet access, run the following in PowerShell to check first-use setup. The test builds and extracts the teacher ZIP, interrupts the Python transfer, selects **Retry** in the setup dialog, and opens the private teacher page. It then stops the launcher and reopens the same package with component downloads blocked.

```powershell
$env:WINDOWS_DOWNLOAD_TEST = '1'
node --test --test-name-pattern="Windows download" tools/check_long_valley.mjs
```

The prepared-shortcut checks on Mac and Windows use a temporary virtual environment. To run those checks offline, download the wheels beforehand with `python -m pip download -r classroom/requirements.txt -d wheels`. Set `PIP_NO_INDEX=1` and set `PIP_FIND_LINKS` to the wheel directory's file URL, for example `file:///C:/classroom%20tests/wheels`.

The spring investigation checks cover alignment changes, bridge supports and tunnel entrances drawn on the map, and inspection of overlap evidence by pointer and keyboard. They also exercise the paired sites, the no-works comparison, replay, reset, and language switching with a design still being edited.

The sharing checks verify in both languages that a teacher can project the original maps and evidence after the group changes its crossing, replays, and resets. They also verify that a new share leaves the selected projection in place and that comparisons are private to the class teacher.

## Building and verifying the Mac download

Use macOS with Xcode selected and Python 3 with pip. To create the ZIP for local testing, run `python3 tools/build_mac_classroom.py /tmp/SiMetropolis-Edu-Mac.zip`. The app includes both Mac architectures and the classroom’s Python dependencies. It downloads a pinned [standalone Python runtime](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110) for the current architecture, verifies its SHA-256, and keeps it in the teacher’s Application Support folder.

Pass `--signing-identity "Developer ID Application: …"` and `--notary-profile PROFILE` together to build the distribution ZIP. The script signs the app, submits it to Apple, and packages it with the stapled ticket. Link the signed and notarized ZIP from the project download page after verifying it on a clean Mac. See [Apple's distribution testing guidance](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).

Run `python3 -B -m unittest discover -s tests -p test_mac_classroom_package.py` to build and inspect the extracted package. Set `SIMETROPOLIS_MAC_TEST_ARCHIVE` to the native tarball listed in `tools/mac_classroom/runtime.json` to also test fresh setup against a local download server and relaunch after taking that server offline.

To check the distribution ZIP, download it in a browser on a clean Mac, extract it in Finder, and double-click **Open SiMetropolis Edu**. Interrupt the runtime transfer and verify **Retry** opens the private teacher page after reconnecting. Quit the launcher, disconnect Wi-Fi and Ethernet, and double-click the same app again. Lesson preparation should open in the browser.
