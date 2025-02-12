# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core import signals


@signals.core.import_tasks.connect
def _import_tasks(sender, **kwargs):
    import indico_jacow.task  # noqa: F401
