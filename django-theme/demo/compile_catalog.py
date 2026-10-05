"""Compile only the demo's zh_Hans catalog. Never touches installed catalogs."""
import argparse
from collections import Counter
import gettext
from io import BytesIO
from pathlib import Path
import re

import polib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in .mo matches .po without writing")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / "locale/zh_Hans/LC_MESSAGES/django.po"
    catalog = polib.pofile(str(source), check_for_duplicates=True)
    spec = re.compile(r"%(?:\([^)]+\))?[#0 +\-]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrsa%]")
    for entry in catalog:
        if entry.obsolete or "fuzzy" in entry.flags or not entry.translated():
            raise ValueError(f"Incomplete project translation: {entry.msgid}")
        for target in entry.msgstr_plural.values() if entry.msgid_plural else (entry.msgstr,):
            if Counter(spec.findall(entry.msgid)) != Counter(spec.findall(target)):
                raise ValueError(f"Mismatched placeholders: {entry.msgid}")
    destination = source.with_suffix(".mo")
    compiled = catalog.to_binary()
    if args.check:
        if not destination.exists() or gettext.GNUTranslations(BytesIO(destination.read_bytes()))._catalog != gettext.GNUTranslations(BytesIO(compiled))._catalog:
            raise SystemExit("Project .mo is missing or stale; run python demo/compile_catalog.py")
        print("Project catalog is current")
    else:
        destination.write_bytes(compiled)
        print(f"Compiled {len(catalog)} project messages to {destination}")


if __name__ == "__main__":
    main()
