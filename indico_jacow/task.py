# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from celery.schedules import crontab

from indico.core.auth import multipass
from indico.core.celery import celery
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User


@celery.periodic_task(run_every=crontab(minute=0))
def sync_profiles():
    from indico_jacow.plugin import JACOWPlugin
    if not JACOWPlugin.settings.get('sync_enabled'):
        JACOWPlugin.logger.info('Profile sync is disabled')
        return

    JACOWPlugin.logger.info('Synchronizing profiles with central database')
    # Sync all users that have a link to the jacow identity provider
    syncable_users = (
        User.query
        .filter(
            ~User.is_system,
            ~User.is_deleted,
            User.identities.any(Identity.provider == multipass.sync_provider.name)
        )
        .order_by(User.id)
        .all()
    )
    for user in syncable_users:
        user.synchronize_data(refresh=True, silent=True)

    # Add identities to users that exist in the central repo but have no
    # corresponding identity (usually pending users that never logged in)
    no_identity_users = (
        User.query
        .filter(
            ~User.is_system,
            ~User.is_deleted,
            ~User.identities.any(Identity.provider == multipass.sync_provider.name)
        )
        .order_by(User.id)
        .all()
    )
    for user in no_identity_users:
        identities = list(multipass.search_identities(providers={multipass.sync_provider.name}, exact=True,
                                                      email=user.email))
        if len(identities) != 1:
            continue
        info = identities[0]
        identity = Identity(provider=info.provider.name, identifier=info.identifier, data=info.data,
                            multipass_data=info.multipass_data)
        user.identities.add(identity)
        user.is_pending = False  # pending users w/ an identity can't log in
        JACOWPlugin.logger.info('Adding identity %r to %r', identity, user)
        db.session.flush()

    db.session.commit()
    JACOWPlugin.logger.info('Sync finished')
