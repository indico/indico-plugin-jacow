# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.plugins import WPJinjaMixinPlugin
from indico.modules.events.management.views import WPEventManagement


class WPAbstractsStats(WPJinjaMixinPlugin, WPEventManagement):
    sidemenu_option = 'abstracts_stats'
