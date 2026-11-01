# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from collections import defaultdict
from statistics import mean, pstdev

from indico.modules.events.abstracts.controllers.abstract_list import RHManageAbstractsExportActionsBase
from indico.modules.events.abstracts.util import generate_spreadsheet_from_abstracts
from indico.modules.events.contributions.controllers.management import RHManageContributionsExportActionsBase
from indico.modules.events.contributions.util import generate_spreadsheet_from_contributions
from indico.util.spreadsheets import send_csv, send_xlsx
from indico.web.flask.util import url_for

from indico_jacow.models.profiles import format_person_initials, format_person_name, uses_full_first_name
from indico_jacow.util import get_ror_id


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


def _append_profile_data_fields(headers, rows, items):
    """Add author data from the users' JACoW profiles (initials, ORCID and ROR IDs)."""
    def name_and_data(person, data):
        name = format_person_name(person)
        data = '; '.join(data)
        return f'{name} ({data})' if data else name

    def name_and_orcid(person):
        profile = person.person.user.jacow_profile if person.person.user else None
        return name_and_data(person, [profile.orcid] if profile and profile.orcid else [])

    def name_and_ror(person):
        return name_and_data(person, [get_ror_id(ja.affiliation) or '-' for ja in person.jacow_affiliations])

    roles = (('Speakers', 'speakers'), ('Primary authors', 'primary_authors'), ('Co-Authors', 'secondary_authors'))
    for title, __ in roles:
        headers.extend((f'{title} (first name)', f'{title} (initials)', f'{title} (full first name)',
                        f'{title} (last name)', f'{title} (ORCID)', f'{title} (ROR)'))

    for idx, item in enumerate(items):
        for title, attr in roles:
            persons = getattr(item, attr)
            rows[idx][f'{title} (first name)'] = [p.first_name for p in persons]
            rows[idx][f'{title} (initials)'] = [format_person_initials(p) for p in persons]
            rows[idx][f'{title} (full first name)'] = ['Yes' if uses_full_first_name(p) else 'No' for p in persons]
            rows[idx][f'{title} (last name)'] = [p.last_name for p in persons]
            rows[idx][f'{title} (ORCID)'] = [name_and_orcid(p) for p in persons]
            rows[idx][f'{title} (ROR)'] = [name_and_ror(p) for p in persons]


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
        _append_profile_data_fields(headers, rows, self.abstracts)

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
        _append_profile_data_fields(headers, rows, self.contribs)
        return headers, rows


class RHContributionsExportCSV(RHContributionsExportBase):
    def _process(self):
        return send_csv('contributions.csv', *self._generate_spreadsheet())


class RHContributionsExportExcel(RHContributionsExportBase):
    def _process(self):
        return send_xlsx('contributions.xlsx', *self._generate_spreadsheet())
