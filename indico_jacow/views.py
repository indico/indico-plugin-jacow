# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.abstracts.views import WPDisplayAbstracts
from indico.modules.events.management.views import WPEventManagement


class WPDisplayAbstractsStatistics(WPJinjaMixinPlugin, WPDisplayAbstracts):
    menu_entry_name = 'abstract_reviewing_stats'
    menu_entry_plugin = 'jacow'


class WPAbstractsStats(WPJinjaMixinPlugin, WPEventManagement):
    sidemenu_option = 'abstracts_stats'
