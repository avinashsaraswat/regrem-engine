"""Write the kit's RELEASE.json: its version, a hash of every file a finding's page depends on, and a
hash of each test asset.

Purpose: `python3 -I finding/release.py 0.7.1` sets a numbered release. With no version it refreshes the
  hashes at the version already in RELEASE.json when nothing moved. When a hash moved it steps to a site
  version, 0.7.1 to 0.7.1+site.1 and then 0.7.1+site.2, so a kit an institution changed never reads as the published
  release; the site change log records each step. `finding --version` and every page read this file, and
  the self-test fails until it is current.
Reads: the files named by KIT_FILES and TEST_ASSETS in finding.py. Writes: RELEASE.json at the kit root.
Network: none. Standard library only, Python 3.9 and later.
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # leave no cache files beside the kit's code
KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "finding"))

import finding  # noqa: E402

VERSION = re.compile(r"\d+(?:\.\d+)*(?:\+site\.\d+)?")
USAGE = "usage: python3 -I finding/release.py [version, such as 0.7.1]"


def next_version(current, files, tests):
    """The version for a refresh with no version named: the same, or the next site version."""
    if files == current.get("files") and tests == current.get("tests"):
        return current["version"]
    base, _, n = current["version"].partition("+site.")
    return "{}+site.{}".format(base, int(n or 0) + 1)


def main(argv):
    if len(argv) > 1 or (argv and not VERSION.fullmatch(argv[0])):
        print(USAGE, file=sys.stderr)
        return 2
    path = KIT / "RELEASE.json"
    try:
        files = {rel: finding.text_digest(KIT / rel) for rel in finding.KIT_FILES}
    except OSError as err:
        print("Refused: {} is missing, so RELEASE.json was left as it is.".format(Path(str(err.filename)).name))
        return 1
    tests = {rel: finding.text_digest(KIT / rel) for rel in finding.test_asset_files()}
    if argv:
        version = argv[0]
    else:
        current = finding.read_release()
        if current is None or not VERSION.fullmatch(str(current.get("version"))):
            print("RELEASE.json is missing or holds no version, so name one: " + USAGE)
            return 1
        version = next_version(current, files, tests)
    was = None if argv else current["version"]
    doc = {"version": version, "files": files, "tests": tests, "regenerate": "python3 -I finding/release.py"}
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("RELEASE.json: {}, {} files, {} test files".format(version, len(files), len(tests)))
    if was is not None and was != version:
        print("A hash moved, so this kit now reads as site version {}. Record it in the site change log. A numbered "
              "release names its version: python3 -I finding/release.py {}.".format(version, version.partition("+site.")[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
