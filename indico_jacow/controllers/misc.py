# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import csv
import io

from flask import jsonify, session
from flask_pluginengine import current_plugin
from marshmallow import fields

from indico.core.db import db
from indico.core.errors import UserValueError
from indico.modules.events.papers.controllers.base import RHManagePapersBase
from indico.modules.users import User
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.schemas import AffiliationSchema
from indico.modules.users.util import search_affiliations
from indico.util.countries import get_country
from indico.util.date_time import now_utc
from indico.util.marshmallow import not_empty, validate_with_message
from indico.util.string import validate_email
from indico.web.args import use_args, use_kwargs
from indico.web.rh import RHProtected

from indico_jacow import _


class RHPeerReviewCSVImport(RHManagePapersBase):
    @use_kwargs({'file': fields.Raw(required=True)}, location='files')
    def _process(self, file):
        file_content = file.read().decode('utf-8')
        csv_file = io.StringIO(file_content)
        reader = csv.DictReader(csv_file)

        if 'Email' not in reader.fieldnames:
            raise UserValueError(_('The CSV file is missing the "Email" column.'))

        emails = set()
        for num_row, row in enumerate(reader, 1):
            email = row['Email'].strip().lower()

            if email and not validate_email(email):
                raise UserValueError(_('Row {row}: invalid email address: {email}').format(row=num_row, email=email))
            if email in emails:
                raise UserValueError(_('Row {}: email address is not unique').format(num_row))
            emails.add(email)

        users = set(User.query.filter(~User.is_deleted, User.all_emails.in_(emails)))
        users_emails = {user.email for user in users}

        if not emails:
            raise UserValueError(_('The "Email" column of the CSV is empty'))
        if not users_emails:
            raise UserValueError(_('No users found with the emails provided'))

        unknown_emails = emails - users_emails

        identifiers = [user.identifier for user in users]

        return jsonify({
            'identifiers': identifiers,
            'unknown_emails': list(unknown_emails)
        })


class RHCreateAffiliation(RHProtected):
    @use_args({
        'name': fields.String(required=True, validate=not_empty),
        'alt_names': fields.List(fields.String(validate=not_empty)),
        'city': fields.String(required=True, validate=not_empty),
        'country_code': fields.String(required=True,
                                      validate=validate_with_message(lambda val: get_country(val) is not None,
                                                                     'Invalid country')),
    })
    def _process(self, data):
        aff = Affiliation.get_or_create_from_data(data)
        if aff in db.session:
            # already exists -> just use that one
            return AffiliationSchema().jsonify(aff)
        aff.meta = {
            'created_by': session.user.id,
            'created_dt': now_utc(False).isoformat(),
            'verified': False,
        }
        db.session.add(aff)
        db.session.flush()
        current_plugin.logger.info('Affiliation %r created by %r', aff, session.user)
        search_affiliations.bump_version()
        return AffiliationSchema().jsonify(aff)
