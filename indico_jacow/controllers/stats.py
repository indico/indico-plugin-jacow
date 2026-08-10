# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import session
from sqlalchemy.orm import load_only
from werkzeug.exceptions import Forbidden

from indico.core.db import db
from indico.modules.events.abstracts.controllers.base import RHAbstractsBase
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractReview
from indico.modules.events.abstracts.util import get_track_reviewer_abstract_counts
from indico.modules.events.management.controllers import RHManageEventBase
from indico.modules.events.tracks.models.tracks import Track

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
