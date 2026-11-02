# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import secrets

from flask import flash, jsonify, redirect, request, session
from flask_pluginengine import current_plugin
from marshmallow import fields
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, ServiceUnavailable

from indico.core.db import db
from indico.core.errors import UserValueError
from indico.core.plugins import url_for_plugin
from indico.modules.logs.models.entries import LogKind, UserLogRealm
from indico.modules.users import User
from indico.modules.users.controllers import RHUserBase
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.schemas import AffiliationSchema
from indico.util.marshmallow import validate_with_message
from indico.web.args import use_kwargs
from indico.web.rh import RHProtected

from indico_jacow import _
from indico_jacow.models.profiles import InitialsFormat, UserAffiliation, UserProfile
from indico_jacow.orcid import (ORCIDError, connect_orcid, disconnect_orcid, exchange_code, get_authorize_url,
                                get_orcid_url, is_orcid_configured, is_orcid_in_use, orcid_base_url)
from indico_jacow.util import get_ror_id, normalize_ror_id, set_ror_id
from indico_jacow.views import WPUserJACoWProfile


def can_manage_affiliations(user):
    return user.is_admin or current_plugin.settings.acls.contains_user('repo_managers', user)


def serialize_affiliation(affiliation):
    return AffiliationSchema().dump(affiliation) | {'ror_id': get_ror_id(affiliation)}


def serialize_profile(user):
    # use an unsaved profile with the default values if the user does not have one yet
    profile = user.jacow_profile or UserProfile(initials_format=InitialsFormat.spaced, full_first_name=False)
    return {
        'orcid': profile.orcid,
        'orcid_url': get_orcid_url(profile.orcid),
        'orcid_connected_dt': profile.orcid_connected_dt.isoformat() if profile.orcid_connected_dt else None,
        'initials_format': profile.initials_format.name,
        'full_first_name': profile.full_first_name,
        'affiliations': [serialize_affiliation(ua.affiliation) for ua in profile.affiliations],
    }


class RHUserJACoWProfileBase(RHUserBase):
    def _check_access(self):
        RHProtected._check_access(self)
        if not self.user.can_be_modified(session.user) and not can_manage_affiliations(session.user):
            raise Forbidden('You cannot modify this user.')


class RHUserJACoWProfile(RHUserJACoWProfileBase):
    def _process(self):
        initials_formats = [{'value': x.name, 'title': x.title} for x in InitialsFormat]
        return WPUserJACoWProfile.render_template('jacow_profile.html', 'jacow_profile', user=self.user,
                                                  profile=serialize_profile(self.user),
                                                  initials_formats=initials_formats,
                                                  ror_meta_key=current_plugin.settings.get('ror_meta_key'),
                                                  can_manage_affiliations=can_manage_affiliations(session.user),
                                                  orcid_configured=is_orcid_configured(),
                                                  can_connect_orcid=(self.user == session.user),
                                                  user_id=request.view_args.get('user_id'))


class RHUserJACoWProfileAPI(RHUserJACoWProfileBase):
    def _process_GET(self):
        return jsonify(serialize_profile(self.user))

    @use_kwargs({
        'affiliation_ids': fields.List(fields.Integer(), load_default=lambda: []),
        'initials_format': fields.Enum(InitialsFormat, load_default=InitialsFormat.spaced),
        'full_first_name': fields.Boolean(load_default=False),
    })
    def _process_PUT(self, affiliation_ids, initials_format, full_first_name):
        profile = self.user.jacow_profile or UserProfile(user=self.user)
        affiliations = self._get_affiliations(profile, affiliation_ids)
        old_affiliation_ids = [ua.affiliation_id for ua in profile.affiliations]
        profile.initials_format = initials_format
        profile.full_first_name = full_first_name
        if [a.id for a in affiliations] != old_affiliation_ids:
            # clear and flush first to avoid violating the unique display order index
            profile.affiliations = []
            db.session.flush()
            profile.affiliations = [UserAffiliation(affiliation=aff, display_order=i)
                                    for i, aff in enumerate(affiliations)]
        self._sync_primary_affiliation(affiliations)
        db.session.flush()

        self.user.log(UserLogRealm.user, LogKind.change, 'JACoW profile', 'Profile updated', session.user,
                      data={'Affiliations': ', '.join(aff.name for aff in affiliations),
                            'Initials format': str(initials_format.title),
                            'Full first name': full_first_name})
        return jsonify(serialize_profile(self.user))

    def _get_affiliations(self, profile, affiliation_ids):
        affiliation_ids = list(dict.fromkeys(affiliation_ids))
        current_ids = {ua.affiliation_id for ua in profile.affiliations}
        # deleted affiliations can stay on the profile, but not be newly added
        query = Affiliation.query.filter(Affiliation.id.in_(affiliation_ids),
                                         ~Affiliation.is_deleted | Affiliation.id.in_(current_ids))
        affiliations = {aff.id: aff for aff in query}
        if len(affiliations) != len(affiliation_ids):
            raise UserValueError(_('Invalid affiliation'))
        return [affiliations[id_] for id_ in affiliation_ids]

    def _sync_primary_affiliation(self, affiliations):
        # keep the core affiliation of the user in sync, so it is used wherever
        # Indico only supports a single affiliation
        if not affiliations or 'affiliation' in self.user.synced_fields:
            return
        primary = affiliations[0]
        if self.user.affiliation_link != primary:
            self.user.affiliation_link = primary
            self.user.affiliation = primary.name


class RHORCIDConnect(RHUserJACoWProfileBase):
    """Send the user to ORCID to sign in and prove they own their ORCID iD."""

    def _check_access(self):
        RHUserJACoWProfileBase._check_access(self)
        if self.user != session.user:
            # only the owner can prove they own an ORCID iD, not an admin acting on their behalf
            raise Forbidden(_('Only the user themselves can connect their ORCID iD.'))
        if not is_orcid_configured():
            raise ServiceUnavailable('ORCID integration is not configured')

    def _process(self):
        state = secrets.token_urlsafe(32)
        session['jacow_orcid_oauth_state'] = state
        return redirect(get_authorize_url(state))


class RHORCIDCallback(RHProtected):
    """Handle the redirect back from ORCID after the user signed in there."""

    def _process(self):
        profile_url = url_for_plugin('jacow.user_jacow_profile')
        expected_state = session.pop('jacow_orcid_oauth_state', None)
        if not expected_state or not secrets.compare_digest(expected_state, request.args.get('state', '')):
            raise BadRequest('Invalid or expired ORCID authorization request')
        if request.args.get('error'):
            # e.g. the user clicked "deny" on ORCID
            flash(_('Your ORCID iD has not been connected.'), 'warning')
            return redirect(profile_url)
        if not (code := request.args.get('code')):
            raise BadRequest('No authorization code received from ORCID')

        try:
            orcid = exchange_code(code)
        except ORCIDError:
            current_plugin.logger.exception('ORCID token exchange failed for %r', session.user)
            flash(_('Could not connect your ORCID iD. Please try again later.'), 'error')
            return redirect(profile_url)
        if is_orcid_in_use(orcid, session.user):
            flash(_('The ORCID iD {orcid} is already connected to another Indico account. If both accounts are '
                    'yours, please ask an administrator to merge them.').format(orcid=orcid), 'error')
            return redirect(profile_url)

        connect_orcid(session.user, orcid)
        db.session.flush()
        session.user.log(UserLogRealm.user, LogKind.positive, 'JACoW profile', 'ORCID iD connected', session.user,
                         data={'ORCID': orcid, 'ORCID server': orcid_base_url()})
        flash(_('Your ORCID iD {orcid} has been connected.').format(orcid=orcid), 'success')
        return redirect(profile_url)


class RHORCIDDisconnect(RHUserJACoWProfileBase):
    def _process_DELETE(self):
        if not (profile := self.user.jacow_profile) or not profile.orcid:
            return jsonify(serialize_profile(self.user))
        orcid = profile.orcid
        disconnect_orcid(self.user)
        db.session.flush()
        self.user.log(UserLogRealm.user, LogKind.negative, 'JACoW profile', 'ORCID iD disconnected', session.user,
                      data={'ORCID': orcid})
        return jsonify(serialize_profile(self.user))


class RHUserProfileAffiliations(RHProtected):
    """Get the JACoW profile affiliations of a user, to use them in author lists."""

    def _process_args(self):
        self.user = User.get(request.view_args['user_id'], is_deleted=False)
        if self.user is None:
            raise NotFound

    def _process(self):
        return jsonify(serialize_profile(self.user)['affiliations'])


class RHAffiliationROR(RHProtected):
    """Set the ROR ID of an affiliation which does not have one (e.g. a manually created one)."""

    def _check_access(self):
        RHProtected._check_access(self)
        if not can_manage_affiliations(session.user):
            raise Forbidden

    def _process_args(self):
        self.affiliation = Affiliation.get_or_404(request.view_args['affiliation_id'])

    @use_kwargs({
        'ror_id': fields.String(required=True, validate=validate_with_message(
            lambda val: not val or normalize_ror_id(val) is not None, _('This is not a valid ROR ID'))),
    })
    def _process(self, ror_id):
        ror_id = normalize_ror_id(ror_id)
        set_ror_id(self.affiliation, ror_id)
        db.session.flush()
        current_plugin.logger.info('ROR ID of %r set to %r by %r', self.affiliation, ror_id, session.user)
        return jsonify(serialize_affiliation(self.affiliation))
