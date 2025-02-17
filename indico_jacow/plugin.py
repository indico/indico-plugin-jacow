# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2025 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from flask import g, session
from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField

from indico.core import signals
from indico.core.db import db
from indico.core.plugins import IndicoPlugin, url_for_plugin
from indico.modules.events.abstracts.fields import AbstractPersonLinkListField
from indico.modules.events.abstracts.forms import AbstractForm
from indico.modules.events.abstracts.models.persons import AbstractPersonLink
from indico.modules.events.abstracts.views import WPDisplayAbstracts, WPManageAbstracts
from indico.modules.events.contributions.fields import ContributionPersonLinkListField
from indico.modules.events.contributions.forms import ContributionForm
from indico.modules.events.contributions.models.persons import ContributionPersonLink
from indico.modules.events.contributions.views import WPContributions, WPManageContributions, WPMyContributions
from indico.modules.events.layout.util import MenuEntryData
from indico.modules.events.models.persons import EventPerson
from indico.modules.events.papers.views import WPManagePapers
from indico.modules.events.persons.forms import ManagePersonListsForm
from indico.modules.events.persons.schemas import PersonLinkSchema
from indico.util.i18n import _
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget
from indico.web.menu import SideMenuItem

from indico_jacow.blueprint import blueprint
from indico_jacow.models.affiliations import AbstractAffiliation, ContributionAffiliation


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
    default_event_settings = {
        'multiple_affiliations': False,
    }

    def init(self):
        super().init()
        self.template_hook('abstract-list-options', self._inject_abstract_export_button)
        self.template_hook('contribution-list-options', self._inject_contribution_export_button)
        self.template_hook('custom-affiliation', self._inject_custom_affiliation)
        self.connect(signals.core.add_form_fields, self._add_person_lists_settings, sender=ManagePersonListsForm)
        self.connect(signals.core.form_validated, self._person_lists_form_validated)
        self.connect(signals.core.form_validated, self._submission_form_validated)
        self.connect(signals.event.person_link_field_extra_params, self._person_link_field_extra_params)
        self.connect(signals.event.person_required_fields, self._person_required_fields)
        self.connect(signals.event.abstract_accepted, self._abstract_accepted)
        self.connect(signals.event.sidemenu, self._extend_event_menu)
        self.connect(signals.menu.items, self._add_sidemenu_item, sender='event-management-sidemenu')
        self.connect(signals.plugin.schema_pre_load, self._person_link_schema_pre_load, sender=PersonLinkSchema)
        self.connect(signals.plugin.schema_post_dump, self._person_link_schema_post_dump, sender=PersonLinkSchema)
        wps = (WPContributions, WPDisplayAbstracts, WPManageAbstracts, WPManageContributions,
               WPMyContributions, WPManagePapers)
        self.inject_bundle('main.js', wps)
        self.inject_bundle('main.css', wps)

    def _inject_abstract_export_button(self, event=None):
        return render_plugin_template('export_button.html',
                                      csv_url=url_for_plugin('jacow.abstracts_csv_export_custom', event),
                                      xlsx_url=url_for_plugin('jacow.abstracts_xlsx_export_custom', event))

    def _inject_contribution_export_button(self, event=None):
        return render_plugin_template('export_button.html',
                                      csv_url=url_for_plugin('jacow.contributions_csv_export_custom', event),
                                      xlsx_url=url_for_plugin('jacow.contributions_xlsx_export_custom', event))

    def _inject_custom_affiliation(self, person):
        if (isinstance(person, (AbstractPersonLink, ContributionPersonLink)) and
                self.event_settings.get(person.person.event, 'multiple_affiliations')):
            return render_plugin_template('custom_affiliation.html', person=person)

    def _add_person_lists_settings(self, form_cls, form_kwargs, **kwargs):
        multiple_affiliations = self.event_settings.get(g.rh.event, 'multiple_affiliations')
        return (
            'multiple_affiliations',
            BooleanField(_('Multiple affiliations'), widget=SwitchWidget(),
                         description=_('Gives submitters the ability to list multiple affiliations per author in '
                                       'abstracts and contributions. Once enabled, this setting cannot be disabled.'),
                         default=multiple_affiliations, render_kw={'disabled': multiple_affiliations})
        )

    def _person_lists_form_validated(self, form, **kwargs):
        if (not isinstance(form, ManagePersonListsForm) or
                not form.ext__multiple_affiliations.data or
                self.event_settings.get(g.rh.event, 'multiple_affiliations')):
            return
        self.event_settings.set(g.rh.event, 'multiple_affiliations', True)
        # Populate tables with the current affiliations
        for target, source in ((AbstractAffiliation, AbstractPersonLink),
                               (ContributionAffiliation, ContributionPersonLink)):
            affiliation_id = db.func.coalesce(source.affiliation_id, EventPerson.affiliation_id)
            db.session.execute(
                target.__table__.insert().from_select(
                    ['person_link_id', 'affiliation_id', 'display_order'],
                    db.select([source.id, affiliation_id, 0])
                    .join(source.person)
                    .filter(
                        affiliation_id.isnot(None),
                        EventPerson.event == g.rh.event,
                        ~source.id.in_(db.select([target.person_link_id]))
                    )
                )
            )

    def _submission_form_validated(self, form, **kwargs):
        if not isinstance(form, (AbstractForm, ContributionForm)):
            return
        if not self.event_settings.get(form.event, 'multiple_affiliations'):
            return
        if isinstance(form, AbstractForm):
            person_links = form.person_links
            affiliations_cls = AbstractAffiliation
        else:
            person_links = form.person_link_data
            affiliations_cls = ContributionAffiliation
        affiliations_ids = g.pop('jacow_affiliations_ids', {})
        for person_link in person_links.data:
            person_affiliations = affiliations_ids.get(person_link.person.email, [])
            if not person_affiliations:
                person_links.errors.append(_('Affiliations are required for everyone'))
                return False
            person_link.jacow_affiliations = []
            db.session.flush()
            person_link.jacow_affiliations = [affiliations_cls(affiliation_id=id, display_order=i)
                                              for i, id in enumerate(person_affiliations)]
        db.session.flush()

    def _person_link_field_extra_params(self, field, **kwargs):
        if (
            isinstance(field, (AbstractPersonLinkListField, ContributionPersonLinkListField)) and
            self.event_settings.get(field.event, 'multiple_affiliations')
        ):
            return {'disable_affiliations': True, 'jacow_affiliations': True}

    def _person_required_fields(self, form, **kwargs):
        if isinstance(form, (AbstractForm, ContributionForm)):
            return ['first_name', 'email']

    def _abstract_accepted(self, abstract, contribution, **kwargs):
        for contrib_person in contribution.person_links:
            abstract_person = next(pl for pl in abstract.person_links if pl.person == contrib_person.person)
            contrib_person.jacow_affiliations = [ContributionAffiliation(affiliation_id=ja.affiliation.id,
                                                                         display_order=ja.display_order)
                                                 for ja in abstract_person.jacow_affiliations]
        db.session.flush()

    def _extend_event_menu(self, sender, **kwargs):
        def _statistics_visible(event):
            if not session.user or not event.has_feature('abstracts'):
                return False
            return any(track.can_review_abstracts(session.user) for track in event.tracks)

        return MenuEntryData(title=_('My Statistics'), name='abstract_reviewing_stats',
                             endpoint='jacow.reviewer_stats', position=1, parent='call_for_abstracts',
                             visible=_statistics_visible)

    def _add_sidemenu_item(self, sender, event, **kwargs):
        if not event.can_manage(session.user) or not event.has_feature('abstracts'):
            return
        return SideMenuItem('abstracts_stats', _('CfA Statistics'),
                            url_for_plugin('jacow.abstracts_stats', event), section='reports')

    def _person_link_schema_pre_load(self, sender, data, **kwargs):
        if hasattr(g, 'jacow_affiliations_ids'):
            g.jacow_affiliations_ids[data['email']] = data.get('jacow_affiliations_ids', [])
        else:
            g.jacow_affiliations_ids = {data['email']: data.get('jacow_affiliations_ids', [])}

    def _person_link_schema_post_dump(self, sender, data, orig, **kwargs):
        if not all(isinstance(p, (AbstractPersonLink, ContributionPersonLink)) for p in orig):
            return
        for person, person_link in zip(data, orig, strict=True):
            person['jacow_affiliations_ids'] = [ja.affiliation.id for ja in person_link.jacow_affiliations]
            person['jacow_affiliations_meta'] = [ja.details for ja in person_link.jacow_affiliations]

    def get_blueprints(self):
        return blueprint
