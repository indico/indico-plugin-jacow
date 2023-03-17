# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import session
from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField

from indico.core import signals
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget
from indico.web.menu import SideMenuItem

from indico_jacow.blueprint import blueprint


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

    def init(self):
        super().init()
        self.template_hook('abstract-list-options', self.inject_export_button)
        self.connect(signals.menu.items, self.add_sidemenu_item, sender='event-management-sidemenu')

    def inject_export_button(self, event=None):
        return render_plugin_template('export_button.html', event=event)

    def add_sidemenu_item(self, sender, event, **kwargs):
        if not event.can_manage(session.user) or not event.has_feature('abstracts'):
            return
        return SideMenuItem('abstracts_stats', _('CfA Statistics'),
                            url_for_plugin('jacow.abstracts_stats', event), section='reports')

    def get_blueprints(self):
        return blueprint
