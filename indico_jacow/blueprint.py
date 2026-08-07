# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import has_request_context, request

from indico.core.plugins import IndicoPluginBlueprint

from indico_jacow.controllers import (RHAbstractsExportCSV, RHAbstractsExportExcel, RHAbstractsStats,
                                      RHContributionsExportCSV, RHContributionsExportExcel, RHCountries,
                                      RHCreateAffiliation, RHDisplayAbstractsStatistics, RHMailingLists,
                                      RHMailingListSubscription, RHPeerReviewCSVImport)


blueprint = IndicoPluginBlueprint('jacow', __name__, url_prefix='/event/<int:event_id>')


# Statistics
blueprint.add_url_rule('/abstracts/reviewing/statistics', 'reviewer_stats', RHDisplayAbstractsStatistics)
blueprint.add_url_rule('/manage/abstracts/statistics', 'abstracts_stats', RHAbstractsStats)

# Custom exports
blueprint.add_url_rule('/manage/abstracts/abstracts_custom.csv', 'abstracts_csv_export_custom',
                       RHAbstractsExportCSV, methods=('POST',))
blueprint.add_url_rule('/manage/abstracts/abstracts_custom.xlsx', 'abstracts_xlsx_export_custom',
                       RHAbstractsExportExcel, methods=('POST',))
blueprint.add_url_rule('/manage/contributions/contributions_custom.csv', 'contributions_csv_export_custom',
                       RHContributionsExportCSV, methods=('POST',))
blueprint.add_url_rule('/manage/contributions/contributions_custom.xlsx', 'contributions_xlsx_export_custom',
                       RHContributionsExportExcel, methods=('POST',))

# Peer reviewing CSV import
blueprint.add_url_rule('/manage/api/papers/jacow-csv-import', 'peer_review_csv_import', RHPeerReviewCSVImport,
                       methods=('POST',))

blueprint.add_url_rule('!/api/jacow/countries', 'countries', RHCountries)
blueprint.add_url_rule('!/api/jacow/affiliation', 'create_affiliation', RHCreateAffiliation, methods=('POST',))


# Mailing lists
with blueprint.add_prefixed_rules('!/user/<int:user_id>', '!/user'):
    blueprint.add_url_rule('/mailing-lists/', 'user_mailing_lists', RHMailingLists)
    blueprint.add_url_rule('/mailing-lists/subscriptions/<int:list_id>', 'user_mailing_lists_subscription',
                           RHMailingListSubscription, methods=('PUT', 'DELETE'))


@blueprint.url_defaults
def _add_user_id(endpoint, values):
    if endpoint.startswith('plugin_jacow.user_mailing_lists') and 'user_id' not in values and has_request_context():
        values['user_id'] = request.view_args.get('user_id')
