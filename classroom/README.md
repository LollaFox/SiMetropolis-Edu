# Long Valley classroom

On a prepared computer, double-click **Open SiMetropolis Edu** (`.command` on Mac, `.cmd` on Windows). The default browser opens lesson preparation, including when the computer is disconnected. Choose English or 繁體中文, then click **Start class** when you are ready. On the classroom network, select **Project join information** to show groups the QR code, link, and short code. Keep the launcher window open while using the classroom.

If you spend more than two minutes choosing a browser profile, the launcher opens a fresh sign-in link for the same classroom. Continue in the new teacher tab.

### Prepare a local checkout

The shortcuts use a Python 3.9 or newer virtual environment named `.venv` beside the launchers. To prepare a checkout for testing, run the commands for your platform from the repository root.

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

The launcher checks open the default-browser URL in Chromium with loopback access, exercise language selection before the teacher starts class, and verify that a second browser cannot reuse the private sign-in link. The shortcut check installs `classroom/requirements.txt` into a temporary package's own virtual environment, then runs the local platform's launcher from a folder with spaces in its name. For an offline test run, download the wheels beforehand with `python -m pip download -r classroom/requirements.txt -d wheels`. Set `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` to the absolute path of that wheels directory when running the tests.

The spring investigation checks cover alignment changes, bridge supports and tunnel entrances drawn on the map, and inspection of overlap evidence by pointer and keyboard. They also exercise the paired sites, the no-works comparison, replay, reset, and language switching with a design still being edited.

The sharing checks verify in both languages that a teacher can project the original maps and evidence after the group changes its crossing, replays, and resets. They also verify that a new share leaves the selected projection in place and that comparisons are private to the class teacher.
