from collections import Counter, defaultdict

from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts
from indico.util.spreadsheets import send_csv


class RHAbstractsExportBase(RHManageAbstractsExportActionsBase):
    def get_scores(self, abstract):
        sums = sum((Counter(review.scores) for review in abstract.reviews), Counter())
        lens = sum((Counter(review.scores.keys()) for review in abstract.reviews), Counter())
        return {question: value / lens[question] for question, value in sums.items()}

    def _generate_spreadsheet(self):
        export_config = self.list_generator.get_list_export_config()
        field_names, rows = generate_spreadsheet_from_abstracts(self.abstracts, export_config['static_item_ids'],
                                                                export_config['dynamic_items'])
        for idx, abstract in enumerate(self.abstracts):
            for question, score in self.get_scores(abstract).items():
                title = f'Question {question.title} (AVG score)'
                field_names.append(title)
                rows[idx][title] = round(score, 1)
            questions = defaultdict(list)
            for review in abstract.reviews:
                for rating in review.ratings:
                    if rating.question.field_type == 'bool':
                        questions[rating.question].append(rating.value)
            for question, values in questions.items():
                for answer in [True, False, None]:
                    title = f'Question {question.title} ({str(answer)})'
                    field_names.append(title)
                    rows[idx][title] = len([v for v in values if v == answer])
        return field_names, rows


class RHAbstractsExportCSV(RHAbstractsExportBase):
    def _process(self):
        return send_csv('abstracts.csv', *self._generate_spreadsheet())


class RHAbstractsExportExcel(RHAbstractsExportBase):
    def _process(self):
        return send_csv('abstracts.xlsx', *self._generate_spreadsheet())
