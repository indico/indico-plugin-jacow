# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest

from indico_jacow.util import format_author_name, format_initials, normalize_orcid, normalize_ror_id


@pytest.mark.parametrize(('value', 'expected'), (
    ('0000-0002-1825-0097', '0000-0002-1825-0097'),
    ('0000000218250097', '0000-0002-1825-0097'),
    ('https://orcid.org/0000-0002-1825-0097', '0000-0002-1825-0097'),
    (' http://www.orcid.org/0000-0002-1825-0097 ', '0000-0002-1825-0097'),
    ('0000-0002-1694-233x', '0000-0002-1694-233X'),
    ('0000-0002-1825-0098', None),  # wrong check digit
    ('0000-0002-1825', None),
    ('', None),
    (None, None),
))
def test_normalize_orcid(value, expected):
    assert normalize_orcid(value) == expected


@pytest.mark.parametrize(('value', 'expected'), (
    ('01ggx4157', '01ggx4157'),
    ('01GGX4157', '01ggx4157'),
    ('https://ror.org/01ggx4157', '01ggx4157'),
    ('01ggx415', None),
    ('11ggx4157', None),
    ('01ggu4157', None),  # 'u' is not part of the crockford base32 alphabet
    ('', None),
    (None, None),
    (123, None),
))
def test_normalize_ror_id(value, expected):
    assert normalize_ror_id(value) == expected


@pytest.mark.parametrize(('first_name', 'hyphenated', 'expected'), (
    ('Nils Johan', False, 'N. J.'),
    ('Nils Johan', True, 'N.-J.'),
    ('Jean-Pierre', False, 'J.-P.'),
    ('Jean-Pierre Marie', False, 'J.-P. M.'),
    ('Jean-Pierre Marie', True, 'J.-P.-M.'),
    ('  nils   johan ', False, 'N. J.'),
    ('Ada', True, 'A.'),
    ('', False, ''),
))
def test_format_initials(first_name, hyphenated, expected):
    assert format_initials(first_name, hyphenated=hyphenated) == expected


@pytest.mark.parametrize(('first_name', 'last_name', 'kwargs', 'expected'), (
    ('Nils Johan', 'Olander', {}, 'N. J. Olander'),
    ('Nils Johan', 'Olander', {'hyphenated': True}, 'N.-J. Olander'),
    ('Nils Johan', 'Olander', {'full_first_name': True}, 'Nils Johan Olander'),
    ('Nils Johan', 'Olander', {'full_first_name': True, 'hyphenated': True}, 'Nils Johan Olander'),
    ('', 'Plato', {}, 'Plato'),
    (None, 'Plato', {'full_first_name': True}, 'Plato'),
))
def test_format_author_name(first_name, last_name, kwargs, expected):
    assert format_author_name(first_name, last_name, **kwargs) == expected
