from wtforms.fields import BooleanField

from indico.core.plugins import IndicoPlugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget


class SettingsForm(IndicoForm):
    sync_enabled = BooleanField(_('Sync profiles'), widget=SwitchWidget(),
                                description=_('Periodically sync user details with the central database'))


class JACOWPlugin(IndicoPlugin):
    """JACoW

    Provides utilities for JACoW Indico
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'sync_enabled': False,
    }
