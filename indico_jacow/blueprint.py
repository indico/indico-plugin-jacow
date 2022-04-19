from indico.core.plugins import IndicoPluginBlueprint
from indico_jacow.controllers import RHAbstractsExportCSV, RHAbstractsExportExcel


blueprint = IndicoPluginBlueprint('jacow', __name__, url_prefix='/event/<int:event_id>')

blueprint.add_url_rule('/manage/abstracts/abstracts_custom.csv', 'abstracts_csv_export_custom',
                       RHAbstractsExportCSV, methods=('POST',))
blueprint.add_url_rule('/manage/abstracts/abstracts_custom.xlsx', 'abstracts_xlsx_export_custom',
                       RHAbstractsExportExcel, methods=('POST',))
