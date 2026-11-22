"""Run the Long Valley classroom or issue a reusable teacher credential."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from .state import TeacherCredentials


def origin(value):
    try:
        url = urlsplit(value)
        host, port = url.hostname, url.port
        if (url.scheme in {"http", "https"} and host
                and port != 0 and url.username is None
                and url.path in {"", "/"} and not url.query and not url.fragment
                and not any(char.isspace() for char in value)):
            host = f"[{host}]" if ":" in host else host.encode("idna").decode("ascii")
            default_port = 443 if url.scheme == "https" else 80
            suffix = f":{port}" if port not in {None, default_port} else ""
            return f"{url.scheme}://{host}{suffix}"
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Use an HTTP(S) origin, such as http://192.168.1.10:8899")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("classroom/.data"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("issue-teacher-credential", help="Print a new teacher credential")
    serve = commands.add_parser("serve", help="Serve the classroom")
    serve.add_argument("--host", help="Bind explicitly instead of discovering the classroom network")
    serve.add_argument("--port", type=int, default=8899)
    serve.add_argument("--public-url", type=origin, help="Origin that group devices use")
    serve.add_argument("--duration-seconds", type=int, default=45 * 60)
    args = parser.parse_args()
    credentials = TeacherCredentials(args.data_dir / "teachers")
    if args.command == "issue-teacher-credential":
        print(credentials.issue())
        return
    if not 0 <= args.port <= 65535 or args.duration_seconds < 1:
        serve.error("Use a port from 0 to 65535 and a positive class duration")
    if args.host not in (None, "127.0.0.1") and args.public_url is None:
        serve.error("--public-url is required when serving other devices")

    from .server import run

    run(args.host, args.port, args.public_url, args.duration_seconds, credentials)


if __name__ == "__main__":
    main()
