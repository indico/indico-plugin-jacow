# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import pytest
from flask import g
from marshmallow import EXCLUDE

from indico.modules.events.abstracts.lists import AbstractListGeneratorManagement
from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.modules.events.abstracts.models.review_questions import AbstractReviewQuestion
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractAction, AbstractReview
from indico.modules.events.contributions.models.persons import ContributionPersonLink
from indico.modules.events.tracks import Track
from indico.modules.users.models.affiliations import Affiliation

from indico_jacow.models.affiliations import ContributionAffiliation


def test_person_link_schema_pre_load_ignores_core_affiliation_for_jacow_affiliations(db, app):
    from indico.modules.events.persons.schemas import PersonLinkSchema

    from indico_jacow.plugin import JACOWPlugin

    affiliations = [
        Affiliation(name='Affiliation One'),
        Affiliation(name='Affiliation Two'),
        Affiliation(name='Affiliation Three'),
    ]
    db.session.add_all(affiliations)
    db.session.flush()
    affiliation_text = '; '.join(affiliation.name for affiliation in affiliations)
    data = {
        'first_name': 'Ada',
        'last_name': 'Lovelace',
        'email': 'ada@example.com',
        'affiliation': affiliation_text,
        'affiliation_id': affiliations[0].id,
        'jacow_affiliations_ids': [affiliation.id for affiliation in affiliations],
    }

    with app.test_request_context():
        JACOWPlugin._person_link_schema_pre_load(None, PersonLinkSchema, data)
        person_link_data = PersonLinkSchema(unknown=EXCLUDE).load(data)

        assert g.jacow_affiliations_ids == {'ada@example.com': [affiliation.id for affiliation in affiliations]}
        assert person_link_data['affiliation'] == affiliation_text


def test_person_link_schema_post_dump_omits_core_affiliation_for_jacow_affiliations(db, app):
    from indico.modules.events.persons.schemas import PersonLinkSchema

    from indico_jacow.plugin import JACOWPlugin

    affiliation = Affiliation(name='Affiliation One')
    db.session.add(affiliation)
    db.session.flush()
    person_link = ContributionPersonLink()
    person_link.jacow_affiliations = [ContributionAffiliation(affiliation=affiliation)]
    data = [{'affiliation_id': affiliation.id, 'affiliation_meta': {'id': affiliation.id}}]

    with app.test_request_context():
        JACOWPlugin._person_link_schema_post_dump(None, PersonLinkSchema, data, [person_link])

        assert 'affiliation_id' not in data[0]
        assert 'affiliation_meta' not in data[0]
        assert data[0]['jacow_affiliations_ids'] == [affiliation.id]


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
