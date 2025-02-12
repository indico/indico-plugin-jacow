# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import csv
import io
from collections import defaultdict
from statistics import mean, pstdev

from flask import jsonify, session
from marshmallow import fields
from sqlalchemy.orm import load_only
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.core.errors import UserValueError
from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.controllers.base import RHAbstractsBase
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractReview
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts, get_track_reviewer_abstract_counts
from indico.modules.events.contributions.controllers.management import RHManageContributionsExportActionsBase
from indico.modules.events.contributions.util import generate_spreadsheet_from_contributions
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.papers.controllers.base import RHManagePapersBase
from indico.modules.events.tracks.models.tracks import Track
from indico.modules.users import User
from indico.util.i18n import _
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.util.string import validate_email
from indico.web.args import use_kwargs
from indico.web.flask.util import url_for

from indico_jacow.views import WPAbstractsStats, WPDisplayAbstractsStatistics


def _get_boolean_questions(event):
    return [question
            for question in event.abstract_review_questions
            if not question.is_deleted and question.field_type == 'bool']


def _get_question_counts(question, user):
    counts = (AbstractReviewRating.query
              .filter_by(question=question)
              .filter(AbstractReviewRating.value[()].astext == 'true')
              .join(AbstractReview)
              .filter_by(user=user)
              .with_entities(AbstractReview.track_id, db.func.count())
              .group_by(AbstractReview.track_id)
              .all())
    counts = {Track.query.get(track): count for track, count in counts}
    counts['total'] = sum(counts.values())
    for group in question.event.track_groups:
        counts[group] = sum(counts[track] for track in group.tracks if track in counts)
    return counts


class RHDisplayAbstractsStatistics(RHAbstractsBase):
    def _check_access(self):
        if not session.user or not any(track.can_review_abstracts(session.user) for track in self.event.tracks):
            raise Forbidden
        RHAbstractsBase._check_access(self)

    def _process(self):
        def _show_item(item):
            if item.is_track_group:
                return any(track.can_review_abstracts(session.user) for track in item.tracks)
            else:
                return item.can_review_abstracts(session.user)

        track_reviewer_abstract_count = get_track_reviewer_abstract_counts(self.event, session.user)
        for group in self.event.track_groups:
            track_reviewer_abstract_count[group] = {}
            for attr in ('total', 'reviewed', 'unreviewed'):
                track_reviewer_abstract_count[group][attr] = sum(track_reviewer_abstract_count[track][attr]
                                                                 for track in group.tracks
                                                                 if track.can_review_abstracts(session.user))
        list_items = [item for item in self.event.get_sorted_tracks() if _show_item(item)]
        question_counts = {question: _get_question_counts(question, session.user)
                           for question in _get_boolean_questions(self.event)}
        return WPDisplayAbstractsStatistics.render_template('reviewer_stats.html', self.event,
                                                            abstract_count=track_reviewer_abstract_count,
                                                            list_items=list_items, question_counts=question_counts)


class RHAbstractsStats(RHManageEventBase):
    """Display reviewing statistics for a given event."""

    def _process(self):
        query = (AbstractReview.query
                 .filter(AbstractReview.abstract.has(event=self.event))
                 .options(load_only('user_id')))
        reviewers = sorted({r.user for r in query}, key=lambda x: x.display_full_name.lower())
        list_items = [item for item in self.event.get_sorted_tracks() if not item.is_track_group or item.tracks]
        review_counts = {
            user: {
                track: counts['reviewed']
                for track, counts in get_track_reviewer_abstract_counts(self.event, user).items()
            }
            for user in reviewers
        }
        for user_review_counts in review_counts.values():
            user_review_counts['total'] = sum(user_review_counts.values())
            for group in self.event.track_groups:
                user_review_counts[group] = sum(user_review_counts[track] for track in group.tracks)

        # get the positive answers to boolean questions
        questions = _get_boolean_questions(self.event)
        question_counts = {}
        for question in questions:
            question_counts[question] = {}
            for user in reviewers:
                question_counts[question][user] = _get_question_counts(question, user)

        abstracts_in_tracks_attrs = {
            'submitted_for': lambda t: len(t.abstracts_submitted),
            'moved_to': lambda t: len(t.abstracts_reviewed - t.abstracts_submitted),
            'final_proposals': lambda t: len(t.abstracts_reviewed),
        }
        abstracts_in_tracks = {track: {k: v(track) for k, v in abstracts_in_tracks_attrs.items()}
                               for track in self.event.tracks}
        abstracts_in_tracks.update({group: {k: sum(abstracts_in_tracks[track][k] for track in group.tracks)
                                            for k in abstracts_in_tracks_attrs}
                                    for group in self.event.track_groups})
        return WPAbstractsStats.render_template('abstracts_stats.html', self.event, reviewers=reviewers,
                                                list_items=list_items, review_counts=review_counts,
                                                questions=questions, question_counts=question_counts,
                                                abstracts_in_tracks=abstracts_in_tracks)


def _append_affiliation_data_fields(headers, rows, items):
    def make_address(affiliation):
        address = ' '.join(filter(None, (affiliation.postcode, affiliation.city)))
        return ', '.join(filter(None, (affiliation.street, address)))

    def full_name_and_data(person, data):
        data = '; '.join(data)
        return f'{person.full_name} ({data})' if data else person.full_name

    def full_name_and_country(person):
        return full_name_and_data(person, [ja.affiliation.country_code for ja in person.jacow_affiliations])

    def full_name_and_address(person):
        return full_name_and_data(person, [make_address(ja.affiliation) for ja in person.jacow_affiliations])

    headers.extend(('Speakers (country)', 'Speakers (address)', 'Primary authors (country)',
                    'Primary authors (address)', 'Co-Authors (country)', 'Co-Authors (address)'))

    for idx, item in enumerate(items):
        rows[idx]['Speakers (country)'] = [full_name_and_country(a) for a in item.speakers]
        rows[idx]['Speakers (address)'] = [full_name_and_address(a) for a in item.speakers]
        rows[idx]['Primary authors (country)'] = [full_name_and_country(a) for a in item.primary_authors]
        rows[idx]['Primary authors (address)'] = [full_name_and_address(a) for a in item.primary_authors]
        rows[idx]['Co-Authors (country)'] = [full_name_and_country(a) for a in item.secondary_authors]
        rows[idx]['Co-Authors (address)'] = [full_name_and_address(a) for a in item.secondary_authors]


class RHAbstractsExportBase(RHManageAbstractsExportActionsBase):
    def get_ratings(self, abstract):
        result = defaultdict(list)
        for review in abstract.reviews:
            for rating in review.ratings:
                result[rating.question].append(rating)
        return result

    def _generate_spreadsheet(self):
        export_config = self.list_generator.get_list_export_config()
        headers, rows = generate_spreadsheet_from_abstracts(self.abstracts, export_config['static_item_ids'],
                                                            export_config['dynamic_items'])
        _append_affiliation_data_fields(headers, rows, self.abstracts)

        def get_question_column(title, value):
            return f'Question {title} ({value!s})'

        questions = [question for question in self.event.abstract_review_questions if not question.is_deleted]
        for question in questions:
            if question.field_type == 'rating':
                headers.append(get_question_column(question.title, 'total count'))
                headers.append(get_question_column(question.title, 'AVG score'))
                headers.append(get_question_column(question.title, 'STD deviation'))
            elif question.field_type == 'bool':
                for answer in [True, False, None]:
                    headers.append(get_question_column(question.title, answer))
        headers.append('URL')

        for idx, abstract in enumerate(self.abstracts):
            ratings = self.get_ratings(abstract)
            for question in questions:
                if question.field_type == 'rating':
                    scores = [r.value for r in ratings.get(question, [])
                              if not r.question.no_score and r.value is not None]
                    rows[idx][get_question_column(question.title, 'total count')] = len(scores)
                    rows[idx][get_question_column(question.title, 'AVG score')] = (round(mean(scores), 1)
                                                                                   if scores else '')
                    rows[idx][get_question_column(question.title, 'STD deviation')] = (round(pstdev(scores), 1)
                                                                                       if len(scores) >= 2 else '')
                elif question.field_type == 'bool':
                    for answer in [True, False, None]:
                        count = len([v for v in ratings.get(question, []) if v.value == answer])
                        rows[idx][get_question_column(question.title, answer)] = count
            rows[idx]['URL'] = url_for('abstracts.display_abstract', abstract, management=False, _external=True)

        return headers, rows


class RHAbstractsExportCSV(RHAbstractsExportBase):
    def _process(self):
        return send_csv('abstracts.csv', *self._generate_spreadsheet())


class RHAbstractsExportExcel(RHAbstractsExportBase):
    def _process(self):
        return send_xlsx('abstracts.xlsx', *self._generate_spreadsheet())


class RHContributionsExportBase(RHManageContributionsExportActionsBase):
    def _generate_spreadsheet(self):
        headers, rows = generate_spreadsheet_from_contributions(self.contribs)
        _append_affiliation_data_fields(headers, rows, self.contribs)
        return headers, rows


class RHContributionsExportCSV(RHContributionsExportBase):
    def _process(self):
        return send_csv('contributions.csv', *self._generate_spreadsheet())


class RHContributionsExportExcel(RHContributionsExportBase):
    def _process(self):
        return send_xlsx('contributions.xlsx', *self._generate_spreadsheet())


class RHPeerReviewCSVImport(RHManagePapersBase):
    @use_kwargs({'file': fields.Field(required=True)}, location='files')
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
