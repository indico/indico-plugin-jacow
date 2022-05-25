from collections import Counter, defaultdict

from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts
from indico.util.spreadsheets import send_csv, send_xlsx


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

        def get_score_column(title):
            return f'Question {title} (AVG score)'

        def get_count_column(title, value):
            return f'Question {title} ({str(value)})'

        questions = [question for question in self.event.abstract_review_questions if not question.is_deleted]
        for question in questions:
            if question.field_type == 'rating':
                field_names.append(f'Question {question.title} (AVG score)')
            elif question.field_type == 'bool':
                for answer in [True, False, None]:
                    field_names.append(f'Question {question.title} ({str(answer)})')

        for idx, abstract in enumerate(self.abstracts):
            ratings = self.get_ratings(abstract)
            for question in questions:
                scores = [r for r in ratings.get(question, [])
                          if not r.question.no_score and r.value is not None]
                rows[idx][get_score_column(question.title)] = round(sum(r.value for r in scores) /
                                                                    len(scores), 1) if scores else 0
                if question.field_type == 'bool':
                    for answer in [True, False, None]:
                        count = len([v for v in ratings.get(question, []) if v.value == answer])
                        rows[idx][get_count_column(question.title, answer)] = count

        return field_names, rows


class RHAbstractsExportCSV(RHAbstractsExportBase):
    def _process(self):
        return send_csv('abstracts.csv', *self._generate_spreadsheet())


class RHAbstractsExportExcel(RHAbstractsExportBase):
    def _process(self):
        return send_xlsx('abstracts.xlsx', *self._generate_spreadsheet())
