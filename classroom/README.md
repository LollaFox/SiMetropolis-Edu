# Long Valley classroom

Run these commands from the repository root with Python 3.9 or newer.

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

Each group can select **Save for swap** to keep the crossing it wants to try at the other site. Once both groups have joined, the teacher can select **Pass the City** to move both groups to their partner sites. The new maps open on each group’s own saved crossing. Groups that skipped saving take their last tested crossing. At the partner site, groups can immediately revise, replay, or reset.

The class lasts 45 minutes by default. **End class** closes it early, and the same credential opens the next class. Credential hashes are stored in `classroom/.data/teachers`. A server restart closes the current class. For a different storage location, pass the same `--data-dir` before both subcommands.

## Group devices

For devices on a trusted local network, bind to the teacher computer’s LAN address and use the same address in the public URL. Replace the example address with the teacher computer’s address, and open the teacher view through that URL. For a server behind an HTTPS reverse proxy, set `--public-url` to the HTTPS origin.

```sh
python -B -m classroom serve --host 192.168.1.10 --public-url http://192.168.1.10:8899
```

## Browser verification

Install Playwright and jsQR in an external test directory. Set `PLAYWRIGHT_PATH` and `JSQR_PATH` to their installed module paths if Node cannot resolve them from the repository. Playwright uses its installed Chromium by default. Set `CHROME_PATH` to use an installed Chrome executable.

```sh
node --test tools/check_long_valley.mjs
```

The tests launch an isolated loopback classroom and use independent browser contexts for teachers and groups. They verify that only the class teacher can load the projection and its QR image. They decode the QR, join both sites, and exercise both languages. They also check manual ending, expiry, a fresh class, and the message shown when a group reopens a closed Traditional Chinese class.

The spring investigation checks cover alignment changes, bridge supports and tunnel entrances drawn on the map, and inspection of overlap evidence by pointer and keyboard. They also exercise the paired sites, the no-works comparison, replay, reset, and language switching with a design still being edited.
