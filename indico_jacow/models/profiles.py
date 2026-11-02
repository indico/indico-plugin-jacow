# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.db.sqlalchemy import PyIntEnum, UTCDateTime, db
from indico.util.enum import RichIntEnum
from indico.util.string import format_repr

from indico_jacow import _
from indico_jacow.util import format_author_name, format_initials


class InitialsFormat(RichIntEnum):
    __titles__ = [_('Separated by spaces (N. J. Olander)'), _('Joined by hyphens (N.-J. Olander)')]
    spaced = 0
    hyphenated = 1


class UserProfile(db.Model):
    """JACoW-specific data stored on a user's profile, shared by all events."""

    __tablename__ = 'user_profiles'
    __table_args__ = {'schema': 'plugin_jacow'}

    user_id = db.Column(
        db.ForeignKey('users.users.id'),
        primary_key=True
    )
    #: The ORCID iD in its canonical ``0000-0000-0000-0000`` form; it is only
    #: ever set after the user signed in at ORCID to prove they own it
    orcid = db.Column(
        db.String,
        nullable=True
    )
    #: When the ORCID iD was connected
    orcid_connected_dt = db.Column(
        UTCDateTime,
        nullable=True
    )
    #: How multiple first names are abbreviated
    initials_format = db.Column(
        PyIntEnum(InitialsFormat),
        nullable=False,
        default=InitialsFormat.spaced
    )
    #: Show the full first name instead of initials (e.g. for names not natively written in Latin script)
    full_first_name = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    user = db.relationship(
        'User',
        lazy=True,
        backref=db.backref(
            'jacow_profile',
            uselist=False,
            lazy=True,
            cascade='all, delete-orphan'
        )
    )

    # relationship backrefs:
    # - affiliations (UserAffiliation.profile)

    def format_name(self, first_name, last_name):
        return format_author_name(first_name, last_name, full_first_name=self.full_first_name,
                                  hyphenated=(self.initials_format == InitialsFormat.hyphenated))

    def __repr__(self):
        return format_repr(self, 'user_id', orcid=None)


class UserAffiliation(db.Model):
    """An affiliation in a user's ordered list of JACoW profile affiliations."""

    __tablename__ = 'user_affiliations'
    __table_args__ = (db.Index(None, 'user_id', 'display_order', unique=True),
                      {'schema': 'plugin_jacow'})

    user_id = db.Column(
        db.ForeignKey('plugin_jacow.user_profiles.user_id'),
        primary_key=True
    )
    affiliation_id = db.Column(
        db.ForeignKey('indico.affiliations.id'),
        primary_key=True
    )
    display_order = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    profile = db.relationship(
        'UserProfile',
        lazy=True,
        backref=db.backref(
            'affiliations',
            order_by=display_order,
            cascade='all, delete-orphan',
            lazy=True
        )
    )
    affiliation = db.relationship(
        'Affiliation',
        lazy=False,
        backref=db.backref(
            'jacow_user_affiliations',
            cascade='all, delete-orphan',
            lazy=True
        )
    )

    @property
    def details(self):
        from indico.modules.users.schemas import AffiliationSchema
        return AffiliationSchema().dump(self.affiliation)

    def __repr__(self):
        return format_repr(self, 'user_id', 'affiliation_id')


def _get_profile(person):
    user = person.person.user if hasattr(person, 'person') else getattr(person, 'user', None)
    return user.jacow_profile if user else None


def format_person_name(person):
    """Format the name of a person (link) using the JACoW profile of the linked user, if any."""
    if profile := _get_profile(person):
        return profile.format_name(person.first_name, person.last_name)
    return format_author_name(person.first_name, person.last_name)


def format_person_initials(person):
    """Get the initials of a person (link), in the initials format of the linked user's JACoW profile."""
    profile = _get_profile(person)
    hyphenated = profile is not None and profile.initials_format == InitialsFormat.hyphenated
    return format_initials(person.first_name or '', hyphenated=hyphenated)


def uses_full_first_name(person):
    """Whether the linked user wants their first name written out instead of as initials."""
    profile = _get_profile(person)
    return profile is not None and profile.full_first_name
