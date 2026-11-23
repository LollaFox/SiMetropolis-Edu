"""Build the universal Mac classroom ZIP with the macOS command line tools."""

import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
MAC = ROOT / "tools/mac_classroom"
APP_NAME = "Open SiMetropolis Edu"
ARCHITECTURES = ("arm64", "x86_64")


def run(*args):
    subprocess.run(args, check=True)


def package_app(app, archive, signing_identity, notary_profile):
    signing_options = ["--options", "runtime", "--timestamp"] if signing_identity else []
    run("/usr/bin/codesign", "--force", "--sign", signing_identity or "-", *signing_options, app)
    run("/usr/bin/ditto", "-c", "-k", "--keepParent", app, archive)
    if notary_profile:
        submission = json.loads(subprocess.check_output([
            "/usr/bin/xcrun", "notarytool", "submit", archive, "--keychain-profile", notary_profile,
            "--wait", "--output-format", "json",
        ]))
        if submission.get("status") != "Accepted":
            raise SystemExit(f"Apple notarization failed: {submission}")
        run("/usr/bin/xcrun", "stapler", "staple", app)
        run("/usr/bin/xcrun", "stapler", "validate", app)
        archive.unlink()
        run("/usr/bin/ditto", "-c", "-k", "--keepParent", app, archive)
        extraction = archive.parent / "verify"
        run("/usr/bin/ditto", "-x", "-k", archive, extraction)
        app = extraction / app.name
        run("/usr/bin/xcrun", "stapler", "validate", app)
        run("/usr/sbin/spctl", "--assess", "--type", "execute", app)
    run("/usr/bin/codesign", "--verify", "--strict", app)


def build(output, signing_identity, notary_profile):
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mac-classroom-", dir=output.parent) as temporary:
        stage = Path(temporary)
        app = stage / f"{APP_NAME}.app"
        contents = app / "Contents"
        resources = contents / "Resources"
        executable = contents / "MacOS" / "OpenSiMetropolisEdu"
        executable.parent.mkdir(parents=True)

        metadata = {
            "CFBundleIdentifier": "org.simetropolis.edu",
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleExecutable": executable.name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        }
        (contents / "Info.plist").write_bytes(plistlib.dumps(metadata))
        lesson = resources / "lesson"
        shutil.copytree(ROOT / "classroom", lesson / "classroom",
                        ignore=shutil.ignore_patterns(".data", "__pycache__", "*.pyc", ".DS_Store"))
        shutil.copy2(ROOT / "LICENSE", resources)
        shutil.copy2(MAC / "runtime.json", resources)
        run(sys.executable, "-m", "pip", "--disable-pip-version-check", "--no-cache-dir", "install",
            "--only-binary=:all:", "--require-hashes", "--no-compile", "--target", lesson,
            "-r", MAC / "wheels.txt", "-r", lesson / "classroom/requirements.txt")
        shutil.rmtree(lesson / "bin", ignore_errors=True)

        for architecture in ARCHITECTURES:
            run("/usr/bin/xcrun", "swiftc", "-O", "-module-cache-path", stage / "swift-cache",
                "-target", f"{architecture}-apple-macos12.0",
                MAC / "LaunchLifetime.swift", MAC / "Launcher.swift", MAC / "main.swift",
                "-o", stage / architecture)
        run("/usr/bin/lipo", "-create", *(stage / arch for arch in ARCHITECTURES), "-output", executable)
        archive = stage / "classroom.zip"
        package_app(app, archive, signing_identity, notary_profile)
        archive.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="where to write SiMetropolis-Edu-Mac.zip")
    parser.add_argument("--signing-identity", help="Developer ID Application identity for a distribution build")
    parser.add_argument("--notary-profile", help="notarytool keychain profile for a distribution build")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("building the Mac package requires macOS")
    if bool(args.signing_identity) != bool(args.notary_profile):
        parser.error("a distribution build requires both --signing-identity and --notary-profile")
    build(args.output.resolve(), args.signing_identity, args.notary_profile)


if __name__ == "__main__":
    main()
