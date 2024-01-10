# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2024 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from sqlalchemy.ext.declarative import declared_attr

from indico.core.db.sqlalchemy import db


class MultipleAffiliationsBase(db.Model):
    """Base class for multiple affiliations associations."""

    __abstract__ = True
    #: The name of the backref on the `Affiliation`
    affiliations_backref_name = None
    #: The name of the foreign key column on the person link table
    person_link_fk = None
    #: The name of the person link class
    person_link_cls = None

    @declared_attr
    def person_link_id(cls):
        return db.Column(
            db.ForeignKey(cls.person_link_fk),
            primary_key=True
        )

    @declared_attr
    def affiliation_id(cls):
        return db.Column(
            db.ForeignKey('indico.affiliations.id'),
            primary_key=True
        )

    @declared_attr
    def person_link(cls):
        return db.relationship(
            cls.person_link_cls,
            uselist=False,
            lazy=False,
            backref=db.backref(
                'jacow_affiliations',
                cascade='all, delete-orphan',
                uselist=True
            )
        )

    @declared_attr
    def affiliation(cls):
        return db.relationship(
            'Affiliation',
            uselist=False,
            lazy=False,
            backref=db.backref(
                cls.affiliations_backref_name,
                cascade='all, delete-orphan',
                uselist=True
            )
        )

    @property
    def details(self):
        from indico.modules.users.schemas import AffiliationSchema
        return AffiliationSchema().dump(self.affiliation)


class AbstractAffiliations(MultipleAffiliationsBase):
    __tablename__ = 'abstract_affiliations'
    __table_args__ = {'schema': 'plugin_jacow'}
    affiliations_backref_name = 'jacow_abstract_affiliations'
    person_link_fk = 'event_abstracts.abstract_person_links.id'
    person_link_cls = 'AbstractPersonLink'


class ContributionAffiliations(MultipleAffiliationsBase):
    __tablename__ = 'contribution_affiliations'
    __table_args__ = {'schema': 'plugin_jacow'}
    affiliations_backref_name = 'jacow_contribution_affiliations'
    person_link_fk = 'events.contribution_person_links.id'
    person_link_cls = 'ContributionPersonLink'
