# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import defaultdict
from statistics import mean, pstdev

from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.web.flask.util import url_for


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
