from indico.modules.events.abstracts.lists import AbstractListGeneratorManagement
from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.modules.events.abstracts.models.review_questions import AbstractReviewQuestion
from indico.modules.events.abstracts.models.review_ratings import AbstractReviewRating
from indico.modules.events.abstracts.models.reviews import AbstractReview, AbstractAction
from indico.modules.events.tracks import Track


def test_get_abstracts(db, app, dummy_event, dummy_user):
    from indico_jacow.controllers import RHAbstractsExportBase
    rh = RHAbstractsExportBase()
    dummy_abstract = Abstract(friendly_id=314,
                              title='Broken Symmetry and the Mass of Gauge Vector Mesons',
                              event=dummy_event,
                              submitter=dummy_user)
    rating_question = AbstractReviewQuestion(field_type='rating', title='Rating')
    bool_question = AbstractReviewQuestion(field_type='bool', title='Bool')
    dummy_event.abstract_review_questions = [rating_question, bool_question]
    first_review = AbstractReview(
        abstract=dummy_abstract, track=Track(title='Dummy Track', event=dummy_event),
        user=dummy_user, proposed_action=AbstractAction.accept
    )
    first_review.ratings = [
        AbstractReviewRating(question=rating_question, value=1),
        AbstractReviewRating(question=bool_question, value=True)
    ]
    second_review = AbstractReview(
        abstract=dummy_abstract, track=Track(title='Dummy Track', event=dummy_event),
        user=dummy_user, proposed_action=AbstractAction.accept
    )
    second_review.ratings = [
        AbstractReviewRating(question=rating_question, value=2),
        AbstractReviewRating(question=bool_question, value=False)
    ]
    db.session.flush()

    rh.event = dummy_event
    rh.abstracts = [dummy_abstract]
    with app.test_request_context():
        rh.list_generator = AbstractListGeneratorManagement(event=dummy_event)
        field_names, rows = rh._generate_spreadsheet()
        assert f'Question {bool_question.title} (AVG score)' not in field_names
        assert rows[0][f'Question {rating_question.title} (AVG score)'] == 1.5
        assert rows[0][f'Question {bool_question.title} (True)'] == 1
        assert rows[0][f'Question {bool_question.title} (False)'] == 1
        assert rows[0][f'Question {bool_question.title} (None)'] == 0
