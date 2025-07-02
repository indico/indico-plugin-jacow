// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

// import getMailingListsURL from 'indico-url:plugin_jacow.mailing_lists';
import mailingListSubscribeURL from 'indico-url:plugin_jacow.mailing_lists_subscribe';
import mailingListUnsubscribeURL from 'indico-url:plugin_jacow.mailing_lists_unsubscribe';

import PropTypes from 'prop-types';
import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import {Button, ListItem, ListContent, List, Checkbox, Modal} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import './MailingList.module.scss';

export function MailingList({mailingLists}) {
  const [lists, setLists] = useState(mailingLists.lists);

  const subscribeList = async listId => {
    try {
      const response = await indicoAxios.post(mailingListSubscribeURL(), {list_id: listId});
      console.log(response.data);
    } catch (e) {
      console.error(e);
    }
  };

  const unsubscribeList = async listsIds => {
    try {
      const response = await indicoAxios.post(mailingListUnsubscribeURL(), {lists_ids: listsIds});
      console.log(response.data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggle = async (ev, {value}) => {
    try {
      setLists(prevLists =>
        prevLists.map(list => {
          if (list.id === value) {
            if (!list.subscribed) {
              subscribeList(value);
            } else {
              unsubscribeList(value);
            }
            return {...list, subscribed: !list.subscribed};
          }
          return list;
        })
      );
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{marginTop: '15px'}}>
      {/* Subscribed Lists Section */}
      <div className="i-box">
        <div className="i-box-header">
          <div className="i-box-title">
            <Translate>My Lists</Translate>
          </div>
        </div>
        <div className="i-box-content">
          <List divided relaxed size="big">
            {lists.map(list => (
              <ListItem className="mailing" key={list.id}>
                <ListContent>
                  <Checkbox
                    label={list.name}
                    value={list.id}
                    onChange={handleToggle}
                    checked={list.subscribed}
                  />
                </ListContent>
              </ListItem>
            ))}
          </List>
        </div>
      </div>
    </div>
  );
}

MailingList.propTypes = {
  mailingLists: PropTypes.shape({
    lists: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.number.isRequired,
        name: PropTypes.string.isRequired,
        subscribed: PropTypes.bool.isRequired,
      })
    ).isRequired,
  }).isRequired,
};

window.setupMailingList = (elem, subMailingLists) => {
  subMailingLists = JSON.parse(subMailingLists);
  ReactDOM.render(<MailingList mailingLists={subMailingLists} />, elem);
};

const ErrorsModal = ({open, onClose, errors}) => {
  return (
    <Modal open={open} onClose={onClose} size="small">
      <Modal.Header>
        <Translate>Subscription/Unsubscription Errors</Translate>
      </Modal.Header>
      <Modal.Content>
        <div>
          <h4>
            <Translate>Failed Actions:</Translate>
          </h4>
          {errors.length > 0 ? (
            <ul>
              {errors.map(error => (
                <li key={error.list_id}>
                  <Translate>List ID:</Translate> {error.list_id} -
                  {error.message || <Translate>Unknown Error</Translate>}
                </li>
              ))}
            </ul>
          ) : (
            <p>
              <Translate>No errors occurred.</Translate>
            </p>
          )}
        </div>
      </Modal.Content>
      <Modal.Actions>
        <Button onClick={onClose} primary>
          <Translate>Close</Translate>
        </Button>
      </Modal.Actions>
    </Modal>
  );
};

ErrorsModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  errors: PropTypes.arrayOf(
    PropTypes.shape({
      list_id: PropTypes.number.isRequired,
      message: PropTypes.string,
    })
  ).isRequired,
};
