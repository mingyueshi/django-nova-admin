"""Validate and compile a selected project PO catalog. Defaults to demo zh_Hans."""
import argparse
from collections import Counter
import gettext
from io import BytesIO
from pathlib import Path
import re

import polib


def runtime_messages(binary):
    translations = gettext.GNUTranslations(BytesIO(binary))
    # GNU msgfmt can drop POT creation timestamps; compare messages and runtime headers.
    headers = tuple(translations.info().get(key) for key in ("language", "content-type", "plural-forms"))
    return headers, {key: value for key, value in translations._catalog.items() if key}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in .mo matches .po without writing")
    parser.add_argument("--po", type=Path, default=Path(__file__).resolve().parent / "locale/zh_Hans/LC_MESSAGES/django.po")
    args = parser.parse_args()
    source = args.po
    catalog = polib.pofile(str(source), check_for_duplicates=True)
    spec = re.compile(r"%(?:\([^)]+\))?[#0 +\-]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diouxXeEfFgGcrsa%]")
    forms = re.fullmatch(r"nplurals\s*=\s*(\d+)\s*;\s*plural\s*=\s*(.+?)\s*;?", catalog.metadata.get("Plural-Forms", "").strip())
    if not forms:
        raise ValueError(f"Missing or invalid Plural-Forms header: {source}")
    indices = set(range(int(forms[1])))
    singular = gettext.c2py(forms[2])(1)
    tokens = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
    for entry in catalog:
        if entry.obsolete or "fuzzy" in entry.flags or not entry.translated():
            raise ValueError(f"Incomplete project translation: {entry.msgid}")
        if entry.msgid_plural and set(entry.msgstr_plural) != indices:
            raise ValueError(f"Incomplete plural forms: {entry.msgid}")
        targets = entry.msgstr_plural.items() if entry.msgid_plural else [(singular, entry.msgstr)]
        for index, target in targets:
            original = entry.msgid if index == singular else entry.msgid_plural
            if (Counter(spec.findall(original)) != Counter(spec.findall(target))
                    or Counter(tokens.findall(original)) != Counter(tokens.findall(target))):
                raise ValueError(f"Mismatched placeholders: {entry.msgid}")
    destination = source.with_suffix(".mo")
    compiled = catalog.to_binary()
    if args.check:
        if not destination.exists() or runtime_messages(destination.read_bytes()) != runtime_messages(compiled):
            raise SystemExit("Project .mo is missing or stale; run python demo/compile_catalog.py")
        print("Project catalog is current")
    else:
        destination.write_bytes(compiled)
        print(f"Compiled {len(catalog)} project messages to {destination}")


if __name__ == "__main__":
    main()
