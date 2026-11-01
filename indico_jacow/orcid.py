# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

"""Connecting ORCID iDs to user profiles using ORCID's OAuth flow.

ORCID iDs are never entered manually. The user signs in at ORCID with the
``/authenticate`` scope, and the iD returned by ORCID's token endpoint is
stored on the profile, so we know the user actually owns it.
"""

from urllib.parse import urlencode

import requests

from indico.core.plugins import url_for_plugin
from indico.modules.users import User
from indico.util.date_time import now_utc

from indico_jacow.models.profiles import UserProfile
from indico_jacow.util import normalize_orcid


ORCID_PRODUCTION_URL = 'https://orcid.org'
ORCID_SANDBOX_URL = 'https://sandbox.orcid.org'


class ORCIDError(Exception):
    pass


def _settings():
    from indico_jacow.plugin import JACOWPlugin
    return JACOWPlugin.settings


def orcid_base_url():
    return ORCID_SANDBOX_URL if _settings().get('orcid_sandbox') else ORCID_PRODUCTION_URL


def get_orcid_url(orcid):
    return f'{orcid_base_url()}/{orcid}' if orcid else None


def is_orcid_configured():
    settings = _settings()
    return bool(settings.get('orcid_client_id') and settings.get('orcid_client_secret'))


def _redirect_uri():
    return url_for_plugin('jacow.orcid_callback', _external=True)


def get_authorize_url(state):
    params = {
        'client_id': _settings().get('orcid_client_id'),
        'response_type': 'code',
        'scope': '/authenticate',
        'redirect_uri': _redirect_uri(),
        'state': state,
    }
    return f'{orcid_base_url()}/oauth/authorize?{urlencode(params)}'


def exchange_code(code):
    """Exchange an authorization code for the ORCID iD of the user who signed in."""
    settings = _settings()
    try:
        resp = requests.post(f'{orcid_base_url()}/oauth/token', timeout=10, headers={'Accept': 'application/json'},
                             data={'client_id': settings.get('orcid_client_id'),
                                   'client_secret': settings.get('orcid_client_secret'),
                                   'grant_type': 'authorization_code',
                                   'redirect_uri': _redirect_uri(),
                                   'code': code})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ORCIDError('Could not get the ORCID iD from ORCID') from exc
    if not (orcid := normalize_orcid(data.get('orcid'))):
        raise ORCIDError('ORCID did not return a valid ORCID iD')
    return orcid


def is_orcid_in_use(orcid, user):
    """Check whether an ORCID iD is already connected to another (non-deleted) user."""
    return (UserProfile.query
            .join(UserProfile.user)
            .filter(UserProfile.orcid == orcid, UserProfile.user_id != user.id, ~User.is_deleted)
            .has_rows())


def connect_orcid(user, orcid):
    profile = user.jacow_profile or UserProfile(user=user)
    profile.orcid = orcid
    profile.orcid_connected_dt = now_utc()
    return profile


def disconnect_orcid(user):
    if profile := user.jacow_profile:
        profile.orcid = None
        profile.orcid_connected_dt = None


def has_connected_orcid(user):
    return bool(user and user.jacow_profile and user.jacow_profile.orcid)
