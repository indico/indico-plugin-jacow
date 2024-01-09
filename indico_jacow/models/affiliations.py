# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from indico.core.db.sqlalchemy import db


class MultipleAffiliations(db.Model):
    __tablename__ = 'multiple_affiliations'
    __table_args__ = {'schema': 'plugin_jacow'}

    person_link_id = db.Column(
        db.ForeignKey('events.contribution_person_links.id'),
        primary_key=True
    )
    affiliation_id = db.Column(
        db.ForeignKey('indico.affiliations.id'),
        primary_key=True
    )

    person_link = db.relationship(
        'ContributionPersonLink',
        uselist=False,
        lazy=False,
        backref=db.backref(
            'affiliations',
            uselist=True
        )
    )
    affiliation = db.relationship(
        'Affiliation',
        uselist=False,
        lazy=False,
        backref=db.backref(
            'multiple_affiliations',
            uselist=True
        )
    )

    @property
    def details(self):
        from indico.modules.users.schemas import AffiliationSchema
        return AffiliationSchema().dump(self.affiliation)
