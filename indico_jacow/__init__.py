from indico.core import signals


@signals.core.import_tasks.connect
def _import_tasks(sender, **kwargs):
    import indico_jacow.task  # noqa: F401
