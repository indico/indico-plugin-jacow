# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import defaultdict
from statistics import mean, pstdev

from sqlalchemy.orm import load_only

from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractReview
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts, get_track_reviewer_abstract_counts
from indico.modules.events.management.controllers import RHManageEventBase
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.web.flask.util import url_for

from indico_jacow.views import WPAbstractsStats


class RHAbstractsStats(RHManageEventBase):
    """Display reviewing statistics for a given event."""

    def _process(self):
        query = (AbstractReview.query
                 .filter(AbstractReview.abstract.has(event=self.event))
                 .options(load_only('user_id')))
        reviewers = sorted({r.user for r in query}, key=lambda x: x.display_full_name.lower())
        list_items = [item for item in self.event.get_sorted_tracks() if not item.is_track_group or item.tracks]
        review_counts = {user: get_track_reviewer_abstract_counts(self.event, user) for user in reviewers}
        for user in review_counts:
            review_counts[user] = {track: review_counts[user][track]['reviewed'] for track in review_counts[user]}
            review_counts[user]['total'] = sum(review_counts[user][track] for track in review_counts[user])
            for group in self.event.track_groups:
                review_counts[user][group] = sum(review_counts[user][track] for track in group.tracks)

        # get the positive answers to boolean questions
        questions = [question
                     for question in self.event.abstract_review_questions
                     if not question.is_deleted and question.field_type == 'bool']
        question_counts = {}
        for question in questions:
            question_counts[question] = {}
            for user in reviewers:
                question_counts[question][user] = {}
                for track in self.event.tracks:
                    query = (AbstractReviewRating.query
                             .filter_by(question=question)
                             .filter(AbstractReviewRating.value[()].astext == 'true')
                             .join(AbstractReview)
                             .filter_by(user=user, track=track))
                    question_counts[question][user][track] = query.count()
                question_counts[question][user]['total'] = sum(question_counts[question][user].values())
                for group in self.event.track_groups:
                    question_counts[question][user][group] = sum(question_counts[question][user][track]
                                                                 for track in group.tracks)
        return WPAbstractsStats.render_template('abstracts_stats.html', self.event, reviewers=reviewers,
                                                list_items=list_items, review_counts=review_counts,
                                                questions=questions, question_counts=question_counts)


class RHAbstractsExportBase(RHManageAbstractsExportActionsBase):
    def get_ratings(self, abstract):
        result = defaultdict(list)
        for review in abstract.reviews:
            for rating in review.ratings:
                result[rating.question].append(rating)
        return result

    def _generate_spreadsheet(self):
        export_config = self.list_generator.get_list_export_config()
        field_names, rows = generate_spreadsheet_from_abstracts(self.abstracts, export_config['static_item_ids'],
                                                                export_config['dynamic_items'])

        def get_question_column(title, value):
            return f'Question {title} ({str(value)})'

        questions = [question for question in self.event.abstract_review_questions if not question.is_deleted]
        for question in questions:
            if question.field_type == 'rating':
                field_names.append(get_question_column(question.title, 'total count'))
                field_names.append(get_question_column(question.title, 'AVG score'))
                field_names.append(get_question_column(question.title, 'STD deviation'))
            elif question.field_type == 'bool':
                for answer in [True, False, None]:
                    field_names.append(get_question_column(question.title, answer))
        field_names.append('URL')

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

        return field_names, rows


class RHAbstractsExportCSV(RHAbstractsExportBase):
    def _process(self):
        return send_csv('abstracts.csv', *self._generate_spreadsheet())


class RHAbstractsExportExcel(RHAbstractsExportBase):
    def _process(self):
        return send_xlsx('abstracts.xlsx', *self._generate_spreadsheet())
