# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re


ORCID_RE = re.compile(r'^(?:https?://(?:www\.)?orcid\.org/)?(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])$', re.IGNORECASE)
# ROR IDs are a leading zero, six Crockford base32 characters and a two-digit checksum
ROR_ID_RE = re.compile(r'^(?:https?://(?:www\.)?ror\.org/)?(0[0-9a-hjkmnp-tv-z]{6}\d{2})$', re.IGNORECASE)


def _orcid_check_digit(base_digits):
    """Calculate the ORCID check digit (ISO 7064 11,2)."""
    total = 0
    for digit in base_digits:
        total = (total + int(digit)) * 2
    result = (12 - total % 11) % 11
    return 'X' if result == 10 else str(result)


def normalize_orcid(value):
    """Normalize an ORCID iD to the ``0000-0000-0000-0000`` form.

    Accepts the bare iD (with or without dashes) or the full ``https://orcid.org/`` URL.
    Returns ``None`` if the value is not a valid ORCID iD (including a wrong check digit).
    """
    match = ORCID_RE.match((value or '').strip())
    if not match:
        return None
    orcid = ''.join(match.groups()).upper()
    if _orcid_check_digit(orcid[:-1]) != orcid[-1]:
        return None
    return '-'.join(orcid[i:i+4] for i in range(0, 16, 4))


def normalize_ror_id(value):
    """Normalize a ROR ID (bare or as ``https://ror.org/`` URL) to its bare lowercase form.

    Returns ``None`` if the value is not a valid ROR ID.
    """
    if not isinstance(value, str):
        return None
    match = ROR_ID_RE.match(value.strip())
    return match.group(1).lower() if match else None


def format_initials(first_name, *, hyphenated=False):
    """Abbreviate a first name to its initials.

    Every given name becomes an initial; names that are hyphenated themselves
    (e.g. Jean-Pierre) always keep the hyphen (J.-P.). Separate given names are
    joined with a space (N. J.), or with a hyphen if `hyphenated` is set (N.-J.).
    """
    initials = []
    for name in first_name.split():
        parts = [part for part in name.split('-') if part]
        if parts:
            initials.append('-'.join(f'{part[0].upper()}.' for part in parts))
    return ('-' if hyphenated else ' ').join(initials)


def format_author_name(first_name, last_name, *, hyphenated=False, full_first_name=False):
    """Format an author name the JACoW way, e.g. ``N. J. Olander``."""
    first_name = (first_name or '').strip()
    last_name = (last_name or '').strip()
    first = ' '.join(first_name.split()) if full_first_name else format_initials(first_name, hyphenated=hyphenated)
    return f'{first} {last_name}'.strip()


def get_ror_id(affiliation):
    """Get the ROR ID stored in an affiliation's metadata, if it has a valid one.

    The metadata key is configured in the plugin settings; a dotted key such as
    ``external_ids.ror`` looks up a nested value.
    """
    from indico_jacow.plugin import JACOWPlugin
    if not affiliation or not (key := JACOWPlugin.settings.get('ror_meta_key')):
        return None
    value = affiliation.meta
    for part in key.split('.'):
        value = value.get(part) if isinstance(value, dict) else None
    return normalize_ror_id(value)


def set_ror_id(affiliation, ror_id):
    """Store a ROR ID in an affiliation's metadata (or remove it if `ror_id` is empty)."""
    from indico_jacow.plugin import JACOWPlugin
    *path, last = JACOWPlugin.settings.get('ror_meta_key').split('.')
    meta = dict(affiliation.meta)
    target = meta
    for part in path:
        target[part] = dict(target.get(part) or {})
        target = target[part]
    if ror_id:
        target[last] = ror_id
    else:
        target.pop(last, None)
    # reassign the whole dict so SQLAlchemy notices the change of the JSONB column
    affiliation.meta = meta
