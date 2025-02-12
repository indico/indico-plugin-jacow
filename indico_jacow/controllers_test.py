# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest

from indico.modules.events.abstracts.lists import AbstractListGeneratorManagement
from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.modules.events.abstracts.models.review_questions import AbstractReviewQuestion
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractAction, AbstractReview
from indico.modules.events.tracks import Track


@pytest.mark.parametrize(('reviews', 'expected'), (
    ((),
     (0, '', '', 0, 0, 0)),
    (((1, True), (2, False)),
     (2, 1.5, 0.5, 1, 1, 0)),
    (((5, None), (None, False)),
     (1, 5, '', 0, 1, 1)),
))
def test_get_abstracts(db, app, dummy_event, dummy_user, reviews, expected):
    from indico_jacow.controllers import RHAbstractsExportBase
    rh = RHAbstractsExportBase()
    dummy_abstract = Abstract(friendly_id=314,
                              title='Broken Symmetry and the Mass of Gauge Vector Mesons',
                              event=dummy_event,
                              submitter=dummy_user)
    rating_question = AbstractReviewQuestion(field_type='rating', title='Rating')
    bool_question = AbstractReviewQuestion(field_type='bool', title='Bool')
    dummy_event.abstract_review_questions = [rating_question, bool_question]
    for review in reviews:
        abstract_review = AbstractReview(
            abstract=dummy_abstract, track=Track(title='Dummy Track', event=dummy_event),
            user=dummy_user, proposed_action=AbstractAction.accept
        )
        abstract_review.ratings = [
            AbstractReviewRating(question=rating_question, value=review[0]),
            AbstractReviewRating(question=bool_question, value=review[1])
        ]
    db.session.flush()

    rh.event = dummy_event
    rh.abstracts = [dummy_abstract]
    with app.test_request_context():
        rh.list_generator = AbstractListGeneratorManagement(event=dummy_event)
        field_names, rows = rh._generate_spreadsheet()
        assert f'Question {bool_question.title} (total count)' not in field_names
        assert f'Question {bool_question.title} (AVG score)' not in field_names
        assert f'Question {bool_question.title} (STD deviation)' not in field_names
        assert rows[0][f'Question {rating_question.title} (total count)'] == expected[0]
        assert rows[0][f'Question {rating_question.title} (AVG score)'] == expected[1]
        assert rows[0][f'Question {rating_question.title} (STD deviation)'] == expected[2]
        assert rows[0][f'Question {bool_question.title} (True)'] == expected[3]
        assert rows[0][f'Question {bool_question.title} (False)'] == expected[4]
        assert rows[0][f'Question {bool_question.title} (None)'] == expected[5]
