# This file is part of the JACoW plugin.
# Copyright (C) 2021 - 2026 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from operator import itemgetter

from brevo import (AddContactToListRequestBodyEmails, Brevo, GetFolder, GetListResponse, GetListsResponseListsItem,
                   NotFoundError, RemoveContactFromListRequestBodyEmails)
from brevo.core import ApiError
from flask import request, session
from flask_pluginengine import current_plugin
from werkzeug.exceptions import Forbidden
from werkzeug.utils import cached_property

from indico.core.errors import IndicoError
from indico.modules.logs.models.entries import LogKind, UserLogRealm
from indico.modules.users.controllers import RHUserBase
from indico.web.rh import RHProtected

from indico_jacow.views import WPUserMailingLists


HIDDEN_FOLDER_PREFIX = 'HIDDEN-'
RESTRICTED_FOLDER_PREFIX = 'RESTRICTED-'


class RHUserMailingListsBase(RHUserBase):
    def _check_access(self):
        RHProtected._check_access(self)
        if (
            not self.user.can_be_modified(session.user) and
            not current_plugin.settings.acls.contains_user('repo_managers', session.user)
        ):
            raise Forbidden('You cannot modify this user.')

    @cached_property
    def brevo_client(self):
        return Brevo(api_key=current_plugin.settings.get('brevo_api_key'), timeout=5)

    def get_contact_info(self, email):
        try:
            return self.brevo_client.contacts.get_contact_info(email)
        except NotFoundError:
            return None
        except ApiError:
            raise IndicoError('Could not get contact info')

    def get_list(self, list_id):
        try:
            return self.brevo_client.contacts.get_list(list_id)
        except ApiError:
            raise IndicoError('Could not get mailing list')

    def get_folder(self, folder_id):
        try:
            return self.brevo_client.contacts.get_folder(folder_id)
        except ApiError:
            raise IndicoError('Could not get mailing list folder')

    def _can_access_mailing_list_folder(self, folder_name: str):
        if folder_name.startswith(HIDDEN_FOLDER_PREFIX):
            return False
        if not folder_name.startswith(RESTRICTED_FOLDER_PREFIX):
            return True
        return session.user.is_admin or current_plugin.settings.acls.contains_user('repo_managers', session.user)

    def check_mailing_list_access(self, mailing_list: GetListResponse):
        folder = self.get_folder(mailing_list.folder_id)
        if not self._can_access_mailing_list_folder(folder.name):
            raise Forbidden

    def get_accessible_list(self, list_id):
        mailing_list = self.get_list(list_id)
        self.check_mailing_list_access(mailing_list)
        return mailing_list

    def group_mailing_lists(
        self,
        mailing_lists: list[GetListsResponseListsItem],
        folders: list[GetFolder],
        subscribed_list_ids: set[int],
    ):
        folder_map = {f.id: f for f in folders}
        groups = {}
        for mailing_list in mailing_lists:
            subscribed = mailing_list.id in subscribed_list_ids
            folder = folder_map[mailing_list.folder_id]
            has_access = self._can_access_mailing_list_folder(folder.name)

            if (not subscribed or folder.name.startswith(HIDDEN_FOLDER_PREFIX)) and not has_access:
                continue

            group = groups.setdefault(folder.id, {
                'key': str(folder.id),
                'title': folder.name.removeprefix(RESTRICTED_FOLDER_PREFIX),
                'restricted': folder.name.startswith(RESTRICTED_FOLDER_PREFIX),
                'has_access': has_access,
                'lists': [],
            })
            group['lists'].append({
                'id': mailing_list.id,
                'name': mailing_list.name,
                'subscribed': subscribed,
            })

        for group in groups.values():
            group['lists'].sort(key=itemgetter('name'))
        return sorted(groups.values(), key=itemgetter('restricted', 'title'))


class RHMailingLists(RHUserMailingListsBase):
    def _process(self):
        subscribed_list_ids = set()
        emails = self.user.all_emails
        lists, folders = self.get_all_lists()

        for email in emails:
            if contact_info := self.get_contact_info(email):
                subscribed_list_ids.update(contact_info.list_ids)

        grouped_lists = self.group_mailing_lists(lists, folders, subscribed_list_ids)
        return WPUserMailingLists.render_template('mailing_lists.html', 'mailing_lists', user=self.user,
                                                  mailing_lists=grouped_lists, user_id=request.view_args.get('user_id'))

    def get_all_lists(self):
        try:
            folders = []
            lists = []
            while chunk := self.brevo_client.contacts.get_folders(offset=len(folders), limit=50).folders:
                folders.extend(chunk)
            while chunk := self.brevo_client.contacts.get_lists(offset=len(lists), limit=50).lists:
                lists.extend(chunk)
        except ApiError:
            raise IndicoError('Could not get mailing lists')
        return lists, folders


class RHMailingListSubscription(RHUserMailingListsBase):
    def _process_PUT(self):
        list_id = request.view_args['list_id']
        email = self.user.email
        mailing_list = self.get_accessible_list(list_id)
        try:
            if self.get_contact_info(email):
                payload = AddContactToListRequestBodyEmails(emails=[email])
                self.brevo_client.contacts.add_contact_to_list(list_id, request=payload)
            else:
                self.brevo_client.contacts.create_contact(
                    email=email,
                    attributes={'FIRSTNAME': self.user.first_name, 'LASTNAME': self.user.last_name},
                    list_ids=[list_id],
                )
        except ApiError as exc:
            if exc.body.get('code') == 'invalid_parameter':
                # Likely "contact already in list" ie the user already subscribed
                return '', 204
            raise IndicoError('Could not subscribe to mailing list')

        self.user.log(UserLogRealm.user, LogKind.positive, 'Mailing Lists',
                      f'Subscribed to list: {mailing_list.name}',
                      session.user, meta={'list_id': list_id})
        return '', 204

    def _process_DELETE(self):
        list_id = request.view_args['list_id']
        mailing_list = self.get_accessible_list(list_id)
        payload = RemoveContactFromListRequestBodyEmails(emails=list(self.user.all_emails))
        try:
            self.brevo_client.contacts.remove_contact_from_list(list_id, request=payload)
        except ApiError as exc:
            if exc.body.get('code') == 'invalid_parameter':
                # Likely "contact already removed" ie the user already unsubscribed
                return '', 204
            raise IndicoError('Could not unsubscribe from mailing list')

        self.user.log(UserLogRealm.user, LogKind.negative, 'Mailing Lists',
                      f'Unsubscribed from list: {mailing_list.name}',
                      session.user, meta={'list_id': list_id})
        return '', 204
