# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os

from flask import g, request, session
from flask_pluginengine import render_plugin_template
from wtforms.fields import BooleanField, StringField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.db import db
from indico.core.errors import UserValueError
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
from indico.modules.events.registration.schemas import CheckinRegistrationSchema
from indico.modules.events.timetable.views import WPManageTimetable
from indico.modules.logs.controllers import RHUserLogs, RHUserLogsJSON
from indico.modules.users import controllers as users_controllers
from indico.modules.users.models.affiliations import Affiliation
from indico.modules.users.views import WPUser
from indico.web.flask.util import url_for
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField, PrincipalListField
from indico.web.forms.widgets import SwitchWidget
from indico.web.menu import SideMenuItem, TopMenuItem

from indico_jacow import _
from indico_jacow.blueprint import blueprint
from indico_jacow.models.affiliations import AbstractAffiliation, ContributionAffiliation
from indico_jacow.models.profiles import UserAffiliation, UserProfile
from indico_jacow.orcid import has_connected_orcid
from indico_jacow.util import get_ror_id


REPO_MANAGER_RHS = (
    users_controllers.RHUsersAdmin,
    users_controllers.RHUsersAdminCreate,
    users_controllers.RHUsersAdminMerge,
    users_controllers.RHUsersAdminMergeCheck,
    users_controllers.RHAffiliationsDashboard,
    users_controllers.RHAffiliationsAPI,
    users_controllers.RHAffiliationAPI,
    users_controllers.RHPersonalData,
    users_controllers.RHPersonalDataUpdate,
    RHUserLogs,
    RHUserLogsJSON,
)


class SettingsForm(IndicoForm):
    _fieldsets = [
        (_('General'), ('brevo_api_key',)),
        (_('User profile management'), ('repo_managers',)),
        (_('Affiliations'), ('ror_meta_key',)),
        (_('ORCID'), ('orcid_client_id', 'orcid_client_secret', 'orcid_sandbox')),
    ]

    repo_managers = PrincipalListField(_('Central Repo Managers'), allow_groups=True,
                                       description=_('List of users who can manage Indico user profiles without being '
                                                     'full Indico admins'))
    brevo_api_key = IndicoPasswordField(_('Brevo API key'), toggle=True)
    ror_meta_key = StringField(_('ROR ID metadata key'), [DataRequired()],
                               description=_('The key in the affiliation metadata which contains the ROR ID of '
                                             'affiliations imported from the ROR registry. Use dots to access '
                                             'nested values, e.g. "external_ids.ror".'))
    orcid_client_id = StringField(_('ORCID client ID'),
                                  description=_('The client ID of your ORCID public API credentials. Users can '
                                                'only connect their ORCID iD when this is set. Register '
                                                '"<indico-url>/jacow/orcid/callback" as redirect URI at ORCID.'))
    orcid_client_secret = IndicoPasswordField(_('ORCID client secret'), toggle=True)
    orcid_sandbox = BooleanField(_('ORCID sandbox'), widget=SwitchWidget(),
                                 description=_('Use the ORCID sandbox (sandbox.orcid.org) instead of the production '
                                               'ORCID registry. Only enable this for testing.'))


class JACOWPlugin(IndicoPlugin):
    """JACoW

    Provides utilities for JACoW Indico
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'brevo_api_key': '',
        'ror_meta_key': 'ror_id',
        'orcid_client_id': '',
        'orcid_client_secret': '',
        'orcid_sandbox': False,
    }
    acl_settings = {
        'repo_managers',
    }
    default_event_settings = {
        'multiple_affiliations': False,
        'require_orcid': False,
        'require_ror': False,
    }

    def init(self):
        super().init()
        self.template_hook('abstract-list-options', self._inject_abstract_export_button)
        self.template_hook('contribution-list-options', self._inject_contribution_export_button)
        self.template_hook('custom-affiliation', self._inject_custom_affiliation)
        self.connect(signals.plugin.get_template_customization_paths, self._override_templates)
        self.connect(signals.core.add_form_fields, self._add_person_lists_settings, sender=ManagePersonListsForm)
        self.connect(signals.core.form_validated, self._person_lists_form_validated)
        self.connect(signals.core.form_validated, self._submission_form_validated)
        self.connect(signals.event.person_link_field_extra_params, self._person_link_field_extra_params)
        self.connect(signals.event.person_required_fields, self._person_required_fields)
        self.connect(signals.event.abstract_accepted, self._abstract_accepted)
        self.connect(signals.event.sidemenu, self._extend_event_menu)
        self.connect(signals.event.contribution_created, self._contribution_created)
        self.connect(signals.event.cloned, self._event_cloned)
        self.connect(signals.event.imported, self._event_imported)
        self.connect(signals.menu.items, self._add_sidemenu_item, sender='event-management-sidemenu')
        self.connect(signals.menu.items, self._add_admin_sidemenu_repo_mgr, sender='admin-sidemenu')
        self.connect(signals.menu.items, self._add_user_sidemenu_repo_mgr, sender='user-profile-sidemenu')
        self.connect(signals.menu.items, self._add_top_menu_repo_mgr, sender='top-menu')
        for rh_cls in REPO_MANAGER_RHS:
            self.connect(signals.rh.before_check_access, self._before_check_access_repo_mgr, sender=rh_cls)
        self.connect(signals.plugin.schema_pre_load, self._person_link_schema_pre_load, sender=PersonLinkSchema)
        self.connect(signals.plugin.schema_post_dump, self._person_link_schema_post_dump, sender=PersonLinkSchema)
        self.connect(signals.menu.items, self._extend_user_profile_menu, sender='user-profile-sidemenu')
        self.connect(signals.plugin.schema_post_dump, self._checkin_registration_schema_post_dump,
                     sender=CheckinRegistrationSchema)
        self.connect(signals.users.merged, self._merge_users)
        self.connect(signals.rh.before_process, self._block_personal_data_affiliation,
                     sender=users_controllers.RHPersonalDataUpdate)
        wps = (WPContributions, WPDisplayAbstracts, WPManageAbstracts, WPManageContributions,
               WPMyContributions, WPManagePapers, WPManageTimetable, WPUser)
        self.inject_bundle('main.js', wps)
        self.inject_bundle('main.css', wps)

    def _override_templates(self, sender, **kwargs):
        return os.path.join(self.root_path, 'template_overrides')

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
        yield (
            'multiple_affiliations',
            BooleanField(_('Multiple affiliations'), widget=SwitchWidget(),
                         description=_('Gives submitters the ability to list multiple affiliations per author in '
                                       'abstracts and contributions. Once enabled, this setting cannot be disabled.'),
                         default=multiple_affiliations, render_kw={'disabled': multiple_affiliations})
        )
        yield (
            'require_orcid',
            BooleanField(_('Require ORCID'), widget=SwitchWidget(),
                         description=_('Only people with an Indico account that is connected to ORCID (in their '
                                       'JACoW profile) can be added as authors or speakers of abstracts and '
                                       'contributions. People who were already added are not affected.'),
                         default=self.event_settings.get(g.rh.event, 'require_orcid'))
        )
        yield (
            'require_ror',
            BooleanField(_('Require ROR'), widget=SwitchWidget(),
                         description=_('Only affiliations with a ROR ID can be added to the authors and speakers of '
                                       'abstracts and contributions. Affiliations that were already added are not '
                                       'affected. Requires multiple affiliations.'),
                         default=self.event_settings.get(g.rh.event, 'require_ror'))
        )

    def _person_lists_form_validated(self, form, **kwargs):
        if not isinstance(form, ManagePersonListsForm):
            return
        # the multiple affiliations switch is disabled (and thus not submitted) once it has been enabled
        multiple_affiliations = (form.ext__multiple_affiliations.data or
                                 self.event_settings.get(g.rh.event, 'multiple_affiliations'))
        if form.ext__require_ror.data and not multiple_affiliations:
            form.ext__require_ror.errors.append(_('ROR IDs can only be required with multiple affiliations.'))
            return False
        self.event_settings.set(g.rh.event, 'require_orcid', form.ext__require_orcid.data)
        self.event_settings.set(g.rh.event, 'require_ror', form.ext__require_ror.data)
        if not form.ext__multiple_affiliations.data or self.event_settings.get(g.rh.event, 'multiple_affiliations'):
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
        if isinstance(form, AbstractForm):
            person_links = form.person_links
            affiliations_cls = AbstractAffiliation
        else:
            person_links = form.person_link_data
            affiliations_cls = ContributionAffiliation
        if self.event_settings.get(form.event, 'require_orcid') and not self._check_orcid_required(person_links):
            return False
        if not self.event_settings.get(form.event, 'multiple_affiliations'):
            return
        affiliations_ids = g.pop('jacow_affiliations_ids', {})
        person_affiliations = []
        for person_link in person_links.data:
            ids = (affiliations_ids.get(person_link.person.email) or
                   self._get_profile_affiliation_ids(person_link.person.user))
            if not ids:
                person_links.errors.append(_('Affiliations are required for everyone'))
                return False
            person_affiliations.append((person_link, ids))
        if (self.event_settings.get(form.event, 'require_ror') and
                not self._check_ror_required(person_links, person_affiliations)):
            return False
        for person_link, ids in person_affiliations:
            person_link.jacow_affiliations = []
            db.session.flush()
            person_link.jacow_affiliations = [affiliations_cls(affiliation_id=id, display_order=i)
                                              for i, id in enumerate(ids)]
        db.session.flush()

    def _check_orcid_required(self, person_links):
        # Only people who are newly added are checked, so existing abstracts and contributions can still
        # be edited after enabling the setting. People already linked to the object have a persistent link.
        missing = [person_link.full_name for person_link in person_links.data
                   if person_link.id is None and not has_connected_orcid(person_link.person.user)]
        if not missing:
            return True
        person_links.errors.append(_('Only people who connected their ORCID iD in their JACoW profile can be added. '
                                     'Missing for: {names}').format(names=', '.join(missing)))
        return False

    def _check_ror_required(self, person_links, person_affiliations):
        # Only newly added affiliations are checked, so existing abstracts and contributions can still be
        # edited after enabling the setting, even if some of their affiliations have no ROR ID.
        new_ids = {id_ for person_link, ids in person_affiliations
                   for id_ in set(ids) - {ja.affiliation_id for ja in person_link.jacow_affiliations}}
        if not new_ids:
            return True
        missing = sorted(aff.name for aff in Affiliation.query.filter(Affiliation.id.in_(new_ids))
                         if not get_ror_id(aff))
        if not missing:
            return True
        person_links.errors.append(_('Only affiliations with a ROR ID can be added. Missing for: {names}')
                                   .format(names=', '.join(missing)))
        return False

    def _get_profile_affiliation_ids(self, user):
        if not user or not user.jacow_profile:
            return []
        return [ua.affiliation_id for ua in user.jacow_profile.affiliations]

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

    def _event_imported(self, target_event, source_event, used_cloners, shared_data, **kwargs):
        # XXX We do not force-enable the `multiple_affiliations` here, because importing from another
        # event is uncommon (probably not used at all on jacow) and enabling this setting silently
        # would be rather strange, especially as it cannot be disabled afterwards.
        if 'contributions' in used_cloners:
            try:
                person_link_map = shared_data['contributions']['person_link_map']
            except (KeyError, TypeError):
                return
            self._clone_contribution_affiliations(person_link_map)

    def _event_cloned(self, event, new_event, used_cloners, shared_data, **kwargs):
        self.event_settings.set(new_event, 'multiple_affiliations',
                                self.event_settings.get(event, 'multiple_affiliations'))
        self.event_settings.set(new_event, 'require_orcid', self.event_settings.get(event, 'require_orcid'))
        if 'contributions' in used_cloners:
            try:
                person_link_map = shared_data['contributions']['person_link_map']
            except (KeyError, TypeError):
                return
            self._clone_contribution_affiliations(person_link_map)

    def _contribution_created(self, contrib, cloned_from=None, person_link_map=None, **kwargs):
        if not cloned_from or g.get('importing_event'):
            # not a clone or importing the timetable/contributions of an event in which case this
            # runs multiple time with the full person link map, and would cause duplicates
            return
        self._clone_contribution_affiliations(person_link_map)

    def _clone_contribution_affiliations(self, person_link_map):
        for old_pl, new_pl in person_link_map.items():
            for x in old_pl.jacow_affiliations:
                # XXX for some reason, during an event clone, the `person_link_id` is sent to the DB as NULL
                # when using the usual `new_pl.jacow_affiliations = ...` way of assigning these objects
                ContributionAffiliation(person_link=new_pl, affiliation=x.affiliation, display_order=x.display_order)

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

    def _is_non_admin_repo_mgr(self):
        return (
            session.user
            and not session.user.is_admin
            and self.settings.acls.contains_user('repo_managers', session.user)
        )

    def _add_admin_sidemenu_repo_mgr(self, sender, **kwargs):
        if self._is_non_admin_repo_mgr():
            yield SideMenuItem('users', _('Users'), url_for('users.users_admin'))
            yield SideMenuItem('affiliations', _('Affiliations'), url_for('users.affiliations_dashboard'))

    def _add_user_sidemenu_repo_mgr(self, sender, user, **kwargs):
        if not self._is_non_admin_repo_mgr():
            return
        if not user.can_be_modified(session.user):
            yield SideMenuItem('personal_data', _('Personal data'), url_for('users.user_profile'), 90)
        yield SideMenuItem('logs', _('Logs'), url_for('logs.user'), -100)

    def _add_top_menu_repo_mgr(self, sender, **kwargs):
        if self._is_non_admin_repo_mgr():
            yield TopMenuItem('admin-jacow-repo', _('JACoW admin'), url_for('users.users_admin'), 65)

    def _before_check_access_repo_mgr(self, sender, rh, **kwargs):
        if session.user and self.settings.acls.contains_user('repo_managers', session.user):
            return True

    def _extend_user_profile_menu(self, sender, user, **kwargs):
        yield SideMenuItem('jacow_profile', _('JACoW profile'), url_for_plugin('jacow.user_jacow_profile'), 70,
                           disabled=user.is_system)
        if self.settings.get('brevo_api_key'):
            yield SideMenuItem('mailing_lists', _('Mailing Lists'),
                               url_for_plugin('jacow.user_mailing_lists'), 65, disabled=user.is_system)

    def _person_link_schema_pre_load(self, sender, data, **kwargs):
        if 'jacow_affiliations_ids' not in data:
            return
        data.pop('affiliation_id', None)
        data.pop('affiliation_link', None)
        jacow_affiliations_ids = g.setdefault('jacow_affiliations_ids', {})
        jacow_affiliations_ids[data['email'].lower()] = data.get('jacow_affiliations_ids', [])

    def _person_link_schema_post_dump(self, sender, data, orig, **kwargs):
        if not self.event_settings.get(g.rh.event, 'multiple_affiliations'):
            return
        if not all(isinstance(p, (AbstractPersonLink, ContributionPersonLink)) for p in orig):
            return
        for person, person_link in zip(data, orig, strict=True):
            if person_link.jacow_affiliations:
                person.pop('affiliation_id', None)
                person.pop('affiliation_meta', None)
            person['jacow_affiliations_ids'] = [ja.affiliation.id for ja in person_link.jacow_affiliations]
            person['jacow_affiliations_meta'] = [ja.details for ja in person_link.jacow_affiliations]

    def _checkin_registration_schema_post_dump(self, sender, data, orig, **kwargs):
        for reg, registration in zip(data, orig, strict=True):
            if not registration.transaction:
                continue
            reg['transaction_amount'] = registration.transaction.amount
            reg['transaction_currency'] = registration.transaction.currency
            reg['transaction_status'] = registration.transaction.status.name

    def _block_personal_data_affiliation(self, sender, rh, **kwargs):
        # affiliations are managed in the JACoW profile, which keeps the core affiliation in sync
        data = request.get_json(silent=True) or {}
        if {'affiliation', 'affiliation_id'} & data.keys():
            raise UserValueError(_('Affiliations can only be changed in the JACoW profile.'))

    def _merge_users(self, target, source, **kwargs):
        self.settings.acls.merge_users(target, source)
        self._merge_profiles(target, source)

    def _merge_profiles(self, target, source):
        if not (source_profile := source.jacow_profile):
            return
        if not (target_profile := target.jacow_profile):
            target.jacow_profile = UserProfile(
                orcid=source_profile.orcid,
                orcid_connected_dt=source_profile.orcid_connected_dt,
                initials_format=source_profile.initials_format,
                full_first_name=source_profile.full_first_name,
                affiliations=[UserAffiliation(affiliation=ua.affiliation, display_order=ua.display_order)
                              for ua in source_profile.affiliations]
            )
        elif not target_profile.orcid:
            target_profile.orcid = source_profile.orcid
            target_profile.orcid_connected_dt = source_profile.orcid_connected_dt
        source.jacow_profile = None

    def get_blueprints(self):
        return blueprint
