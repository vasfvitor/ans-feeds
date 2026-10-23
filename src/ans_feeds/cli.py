"""Command line: `ans-feeds build` rebuilds the whole site from the committed snapshots."""

import argparse
from pathlib import Path

BASE_URL = "https://ans.feeds.abelhaninja.de"
# Fixed forever: feed readers show every entry again when ids change.
BASE_TAG = "ans.feeds.abelhaninja.de,2026:feeds"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ans-feeds")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="rebuild the site and feeds from the snapshots")
    build.add_argument("--snapshots", type=Path, default=Path("snapshots"))
    build.add_argument("--site", type=Path, default=Path("site"))
    build.add_argument("--base-url", default=BASE_URL)
    build.add_argument("--base-tag", default=BASE_TAG)
    build.add_argument("--notice", default=None, help="warning shown on every page")
    args = parser.parse_args(argv)

    if args.command == "build":
        from .site import build_site

        meta = build_site(
            args.snapshots,
            args.site,
            base_url=args.base_url.rstrip("/"),
            base_tag=args.base_tag,
            notice=args.notice,
        )
        print(f"{args.site}: {meta['eventos']} eventos, dados de {meta['date']}")
