# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import IndicoPluginBlueprint

from indico_jacow.controllers import (RHAbstractsExportCSV, RHAbstractsExportExcel, RHAbstractsStats,
                                      RHContributionsExportCSV, RHContributionsExportExcel,
                                      RHDisplayAbstractsStatistics, RHPeerReviewManagersImport)


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
blueprint.add_url_rule('/manage/peer_review/managers/upload', 'peer_review_managers_import',
                       RHPeerReviewManagersImport, methods=('POST',))
