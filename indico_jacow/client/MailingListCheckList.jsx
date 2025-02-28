// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import getMailingListsURL from 'indico-url:plugin_jacow.mailing_lists';
import mailingListSubscribeURL from 'indico-url:plugin_jacow.mailing_lists_subscribe';
import mailingListUnsubscribeURL from 'indico-url:plugin_jacow.mailing_lists_unsubscribe';

// import PropTypes from 'prop-types'
import React, {useState, useEffect} from 'react';
import ReactDOM from 'react-dom';
import {Button, ListItem, Icon, ListContent, List} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import './MailingListCheckList.module.scss';

export function MailingListCheckList() {
  const [mailingLists, setMailingLists] = useState([]);

  useEffect(() => {
    const fetchMailingLists = async () => {
      try {
        const response = await indicoAxios.get(getMailingListsURL());
        setMailingLists(response.data.lists);
      } catch (err) {
        console.error(err);
      }
    };
    fetchMailingLists();
  }, []);

  const subscribeList = async listId => {
    try {
      const response = await indicoAxios.post(mailingListSubscribeURL({list_id: listId}));
      if (response.status === 200) {
        setMailingLists(prevLists =>
          prevLists.map(list => (list.id === listId ? {...list, subscribed: true} : list))
        );
      }
    } catch (e) {
      console.error(e);
    }
  };

  const unsubscribeList = async listId => {
    try {
      const response = await indicoAxios.post(mailingListUnsubscribeURL({list_id: listId}));
      if (response.status === 200) {
        setMailingLists(prevLists =>
          prevLists.map(list => (list.id === listId ? {...list, subscribed: false} : list))
        );
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="i-box" style={{marginTop: '15px'}}>
      <div className="i-box-header">
        <div className="i-box-title">
          <Translate>Mailing Subscriptions</Translate>
        </div>
      </div>
      <div className="i-box-content">
        <List divided size="big">
          {mailingLists.map(list => (
            <ListItem className="mailing" key={list.id}>
              <ListContent>{list.name}</ListContent>
              <ListContent>
                {list.subscribed ? (
                  <Button
                    icon
                    labelPosition="left"
                    className="subscribe-btn"
                    onClick={() => unsubscribeList(list.id)}
                  >
                    <Icon name="minus" />
                    <Translate>Unsubscribe</Translate>
                  </Button>
                ) : (
                  <Button
                    icon
                    labelPosition="left"
                    primary
                    className="subscribe-btn"
                    onClick={() => subscribeList(list.id)}
                  >
                    <Icon name="plus" />
                    <Translate>Subscribe</Translate>
                  </Button>
                )}
              </ListContent>
            </ListItem>
          ))}
        </List>
      </div>
    </div>
  );
}
MailingListCheckList.propTypes = {};

window.setupMailingListChecklist = elem => {
  ReactDOM.render(<MailingListCheckList />, elem);
};
