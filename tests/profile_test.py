# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from indico.modules.events.contributions.models.persons import AuthorType, ContributionPersonLink
from indico.modules.events.models.persons import EventPerson
from indico.modules.users.models.affiliations import Affiliation

from indico_jacow.models.affiliations import ContributionAffiliation
from indico_jacow.models.profiles import (InitialsFormat, UserAffiliation, UserProfile, format_person_name,
                                          uses_full_first_name)
from indico_jacow.orcid import (ORCIDError, connect_orcid, disconnect_orcid, exchange_code, get_authorize_url,
                                has_connected_orcid, is_orcid_configured, is_orcid_in_use)
from indico_jacow.util import get_ror_id, set_ror_id


@pytest.fixture(autouse=True)
def plugin_context():
    from indico_jacow.plugin import JACOWPlugin

    with JACOWPlugin.instance.plugin_context():
        yield


@pytest.fixture
def affiliations(db):
    affiliations = [
        Affiliation(name='CERN', meta={'ror_id': 'https://ror.org/01ggx4157'}),
        Affiliation(name='ESS', meta={'ror_id': '01wv9cn34'}),
        Affiliation(name='Manually added', meta={'created_by': 1, 'verified': False}),
    ]
    db.session.add_all(affiliations)
    db.session.flush()
    return affiliations


def test_get_ror_id(affiliations):
    cern, ess, manual = affiliations
    assert get_ror_id(cern) == '01ggx4157'
    assert get_ror_id(ess) == '01wv9cn34'
    assert get_ror_id(manual) is None
    assert get_ror_id(None) is None


def test_get_ror_id_nested_key(affiliations):
    from indico_jacow.plugin import JACOWPlugin

    JACOWPlugin.settings.set('ror_meta_key', 'external_ids.ror')
    cern = affiliations[0]
    assert get_ror_id(cern) is None
    cern.meta = {'external_ids': {'ror': '01ggx4157'}}
    assert get_ror_id(cern) == '01ggx4157'


def test_set_ror_id(db, affiliations):
    from indico_jacow.plugin import JACOWPlugin

    manual = affiliations[2]
    set_ror_id(manual, '05x2bcf33')
    db.session.flush()
    assert manual.meta == {'created_by': 1, 'verified': False, 'ror_id': '05x2bcf33'}
    assert get_ror_id(manual) == '05x2bcf33'
    set_ror_id(manual, None)
    assert manual.meta == {'created_by': 1, 'verified': False}

    JACOWPlugin.settings.set('ror_meta_key', 'external_ids.ror')
    set_ror_id(manual, '05x2bcf33')
    assert manual.meta['external_ids'] == {'ror': '05x2bcf33'}
    assert get_ror_id(manual) == '05x2bcf33'


@pytest.mark.parametrize(('initials_format', 'full_first_name', 'expected'), (
    (None, False, 'N. J. Olander'),
    (InitialsFormat.spaced, False, 'N. J. Olander'),
    (InitialsFormat.hyphenated, False, 'N.-J. Olander'),
    (InitialsFormat.hyphenated, True, 'Nils Johan Olander'),
))
def test_format_person_name(db, dummy_event, create_user, initials_format, full_first_name, expected):
    user = create_user(123, first_name='Nils Johan', last_name='Olander')
    if initials_format is not None:
        user.jacow_profile = UserProfile(initials_format=initials_format, full_first_name=full_first_name)
    person = EventPerson.create_from_user(user, dummy_event)
    with db.session.no_autoflush:
        person_link = ContributionPersonLink(person=person)
        assert format_person_name(person_link) == expected
        assert uses_full_first_name(person_link) == full_first_name


def test_profile_affiliations_order(db, create_user, affiliations):
    user = create_user(123)
    cern, ess, __ = affiliations
    user.jacow_profile = UserProfile(affiliations=[UserAffiliation(affiliation=ess, display_order=1),
                                                   UserAffiliation(affiliation=cern, display_order=0)])
    db.session.flush()
    db.session.expire(user.jacow_profile)
    assert [ua.affiliation for ua in user.jacow_profile.affiliations] == [cern, ess]


def test_profile_affiliation_ids_fallback(db, create_user, affiliations):
    from indico_jacow.plugin import JACOWPlugin

    user = create_user(123)
    cern, ess, __ = affiliations
    assert JACOWPlugin.instance._get_profile_affiliation_ids(None) == []
    assert JACOWPlugin.instance._get_profile_affiliation_ids(user) == []
    user.jacow_profile = UserProfile(affiliations=[UserAffiliation(affiliation=ess, display_order=0),
                                                   UserAffiliation(affiliation=cern, display_order=1)])
    db.session.flush()
    assert JACOWPlugin.instance._get_profile_affiliation_ids(user) == [ess.id, cern.id]


@pytest.mark.parametrize('target_has_profile', (False, True))
def test_merge_profiles(db, create_user, affiliations, target_has_profile):
    from indico_jacow.plugin import JACOWPlugin

    source = create_user(1)
    target = create_user(2)
    cern = affiliations[0]
    source.jacow_profile = UserProfile(orcid='0000-0002-1825-0097', initials_format=InitialsFormat.hyphenated,
                                       affiliations=[UserAffiliation(affiliation=cern)])
    connect_orcid(source, '0000-0002-1825-0097')
    if target_has_profile:
        target.jacow_profile = UserProfile(full_first_name=True)
    db.session.flush()

    JACOWPlugin.instance._merge_profiles(target, source)
    db.session.flush()

    assert source.jacow_profile is None
    assert target.jacow_profile.orcid == '0000-0002-1825-0097'
    assert target.jacow_profile.orcid_connected_dt is not None
    if target_has_profile:
        # existing settings of the target are kept
        assert target.jacow_profile.full_first_name
        assert target.jacow_profile.initials_format == InitialsFormat.spaced
        assert target.jacow_profile.affiliations == []
    else:
        assert target.jacow_profile.initials_format == InitialsFormat.hyphenated
        assert [ua.affiliation for ua in target.jacow_profile.affiliations] == [cern]
    assert UserProfile.query.count() == 1


def test_export_profile_data(db, dummy_contribution, create_user, affiliations):
    cern, __, manual = affiliations
    user = create_user(123, first_name='Nils Johan', last_name='Olander')
    user.jacow_profile = UserProfile(orcid='0000-0002-1825-0097', initials_format=InitialsFormat.hyphenated)
    person = EventPerson.create_from_user(user, dummy_contribution.event)
    person_link = ContributionPersonLink(person=person, is_speaker=True, author_type=AuthorType.primary)
    person_link.jacow_affiliations = [ContributionAffiliation(affiliation=cern, display_order=0),
                                      ContributionAffiliation(affiliation=manual, display_order=1)]
    other = EventPerson(event=dummy_contribution.event, first_name='Ada', last_name='Lovelace',
                        email='ada@example.com')
    db.session.add_all([person, other])
    other_link = ContributionPersonLink(person=other, author_type=AuthorType.secondary)
    # loading the old person links would autoflush while the new links are not in the session yet
    with db.session.no_autoflush:
        dummy_contribution.person_links = [person_link, other_link]
    db.session.flush()

    # imported here since importing controllers during test collection breaks model setup
    from indico_jacow.controllers.export import _append_profile_data_fields

    headers = []
    rows = [{}]
    _append_profile_data_fields(headers, rows, [dummy_contribution])

    assert 'Primary authors (ORCID)' in headers
    row = rows[0]
    assert row['Speakers (first name)'] == ['Nils Johan']
    assert row['Speakers (initials)'] == ['N.-J.']
    assert row['Speakers (full first name)'] == ['No']
    assert row['Speakers (last name)'] == ['Olander']
    assert row['Primary authors (ORCID)'] == ['N.-J. Olander (0000-0002-1825-0097)']
    assert row['Primary authors (ROR)'] == ['N.-J. Olander (01ggx4157; -)']
    assert row['Co-Authors (first name)'] == ['Ada']
    assert row['Co-Authors (initials)'] == ['A.']
    assert row['Co-Authors (full first name)'] == ['No']
    assert row['Co-Authors (last name)'] == ['Lovelace']
    assert row['Co-Authors (ORCID)'] == ['A. Lovelace']
    assert row['Co-Authors (ROR)'] == ['A. Lovelace']


@pytest.fixture
def orcid_settings():
    from indico_jacow.plugin import JACOWPlugin

    JACOWPlugin.settings.set_multi({'orcid_client_id': 'APP-123', 'orcid_client_secret': 's3cret'})


@pytest.mark.usefixtures('request_context')
def test_orcid_authorize_url(orcid_settings):
    from indico_jacow.plugin import JACOWPlugin

    assert is_orcid_configured()
    url = urlsplit(get_authorize_url('some-state'))
    assert f'{url.scheme}://{url.netloc}{url.path}' == 'https://orcid.org/oauth/authorize'
    params = parse_qs(url.query)
    assert params['client_id'] == ['APP-123']
    assert params['scope'] == ['/authenticate']
    assert params['state'] == ['some-state']
    assert params['redirect_uri'][0].endswith('/jacow/orcid/callback')

    JACOWPlugin.settings.set('orcid_sandbox', True)
    assert get_authorize_url('x').startswith('https://sandbox.orcid.org/oauth/authorize?')


def test_orcid_not_configured():
    assert not is_orcid_configured()


class _FakeResponse:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f'{self.status}')

    def json(self):
        return self.data


@pytest.mark.usefixtures('request_context', 'orcid_settings')
@pytest.mark.parametrize(('response', 'expected'), (
    (_FakeResponse({'orcid': '0000-0002-1825-0097', 'name': 'Josiah Carberry'}), '0000-0002-1825-0097'),
    (_FakeResponse({'orcid': '0000-0002-1825-0098'}), None),  # invalid checksum
    (_FakeResponse({}), None),
    (_FakeResponse({'error': 'invalid_grant'}, status=400), None),
))
def test_orcid_exchange_code(mocker, response, expected):
    post = mocker.patch('indico_jacow.orcid.requests.post', return_value=response)
    if expected is None:
        with pytest.raises(ORCIDError):
            exchange_code('the-code')
    else:
        assert exchange_code('the-code') == expected
    data = post.call_args.kwargs['data']
    assert data['code'] == 'the-code'
    assert data['grant_type'] == 'authorization_code'
    assert data['client_secret'] == 's3cret'


@pytest.mark.usefixtures('request_context', 'orcid_settings')
def test_orcid_exchange_code_connection_error(mocker):
    mocker.patch('indico_jacow.orcid.requests.post', side_effect=requests.ConnectionError)
    with pytest.raises(ORCIDError):
        exchange_code('the-code')


def test_connect_disconnect_orcid(db, create_user):
    user = create_user(1)
    other = create_user(2)
    assert not has_connected_orcid(user)
    connect_orcid(user, '0000-0002-1825-0097')
    db.session.flush()
    assert has_connected_orcid(user)
    assert user.jacow_profile.orcid_connected_dt is not None
    assert not is_orcid_in_use('0000-0002-1825-0097', user)
    assert is_orcid_in_use('0000-0002-1825-0097', other)
    user.is_deleted = True
    db.session.flush()
    assert not is_orcid_in_use('0000-0002-1825-0097', other)
    disconnect_orcid(user)
    assert not has_connected_orcid(user)
    assert user.jacow_profile.orcid_connected_dt is None


def test_check_orcid_required(db, create_user):
    from indico_jacow.plugin import JACOWPlugin

    connected = create_user(1, first_name='Con', last_name='Nected')
    connect_orcid(connected, '0000-0002-1825-0097')
    not_connected = create_user(2)
    db.session.flush()

    def _link(user, id_=None, name='Some Person'):
        return SimpleNamespace(id=id_, full_name=name, person=SimpleNamespace(user=user))

    field = SimpleNamespace(data=[_link(connected), _link(not_connected, id_=42)], errors=[])
    # already linked people are not checked
    assert JACOWPlugin.instance._check_orcid_required(field)
    assert not field.errors

    field = SimpleNamespace(data=[_link(connected), _link(not_connected, name='Guinea Pig'),
                                  _link(None, name='No Account')], errors=[])
    assert not JACOWPlugin.instance._check_orcid_required(field)
    assert len(field.errors) == 1
    assert 'Guinea Pig, No Account' in field.errors[0]


@pytest.mark.parametrize(('data', 'blocked'), (
    ({'phone': '123'}, False),
    ({'affiliation': 'Free text'}, True),
    ({'affiliation': 'CERN', 'affiliation_id': 1}, True),
    (None, False),
))
def test_block_personal_data_affiliation(app, data, blocked):
    from indico.core.errors import UserValueError

    from indico_jacow.plugin import JACOWPlugin

    with app.test_request_context(method='PATCH', json=data):
        if blocked:
            with pytest.raises(UserValueError):
                JACOWPlugin.instance._block_personal_data_affiliation(None, rh=None)
        else:
            JACOWPlugin.instance._block_personal_data_affiliation(None, rh=None)


def test_check_ror_required(affiliations):
    from indico_jacow.plugin import JACOWPlugin

    cern, ess, manual = affiliations
    existing = SimpleNamespace(jacow_affiliations=[SimpleNamespace(affiliation_id=manual.id)])
    new = SimpleNamespace(jacow_affiliations=[])

    field = SimpleNamespace(errors=[])
    # affiliations which were already set are not checked
    assert JACOWPlugin.instance._check_ror_required(field, [(existing, [manual.id, cern.id]), (new, [ess.id])])
    assert not field.errors

    field = SimpleNamespace(errors=[])
    assert not JACOWPlugin.instance._check_ror_required(field, [(existing, [cern.id]), (new, [ess.id, manual.id])])
    assert len(field.errors) == 1
    assert 'Missing for: Manually added' in field.errors[0]
