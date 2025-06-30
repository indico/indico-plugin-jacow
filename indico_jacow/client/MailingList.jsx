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
import {Button, ListItem, Icon, ListContent, List, Checkbox} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import './MailingList.module.scss';

export function MailingList({mailingLists}) {
  const [subMailingLists, setSubMailingLists] = useState(
    mailingLists.lists.filter(list => list.subscribed)
  );
  const [notSubMailingLists, setNotSubMailingLists] = useState(
    mailingLists.lists.filter(list => !list.subscribed)
  );
  const [selectedSubscribed, setSelectedSubscribed] = useState([]);
  const [selectedNotSubscribed, setSelectedNotSubscribed] = useState([]);

  const subscribeList = async listsIds => {
    try {
      const response = await indicoAxios.post(mailingListSubscribeURL(), {lists_ids: listsIds});
      const {results, errors} = response.data;
      console.log(response.data);

      const successfullySubscribed = results.map(result => result.list_id);

      setNotSubMailingLists(prevLists =>
        prevLists.filter(list => !successfullySubscribed.includes(list.id))
      );
      setSubMailingLists(prevLists =>
        prevLists.concat(
          mailingLists.lists.filter(list => successfullySubscribed.includes(list.id))
        )
      );
    } catch (e) {
      console.error(e);
    }
  };

  const unsubscribeList = async listsIds => {
    try {
      const response = await indicoAxios.post(mailingListUnsubscribeURL(), {lists_ids: listsIds});
      const {results, errors} = response.data;
      console.log(response);
      const successfullyUnsubscribed = results.map(result => result.list_id);

      setSubMailingLists(prevLists =>
        prevLists.filter(list => !successfullyUnsubscribed.includes(list.id))
      );
      setNotSubMailingLists(prevLists =>
        prevLists.concat(
          mailingLists.lists.filter(list => successfullyUnsubscribed.includes(list.id))
        )
      );
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectSubscribed = (e, {value}) => {
    setSelectedSubscribed(prev =>
      prev.includes(value) ? prev.filter(id => id !== value) : [...prev, value]
    );
  };

  const handleSelectNotSubscribed = (e, {value}) => {
    setSelectedNotSubscribed(prev =>
      prev.includes(value) ? prev.filter(id => id !== value) : [...prev, value]
    );
  };

  return (
    <div style={{marginTop: '15px'}}>
      {/* Subscribed Lists Section */}
      <div className="i-box">
        <div className="i-box-header">
          <div className="i-box-title">
            <Translate>Subscribed Lists</Translate>
          </div>
        </div>
        <div className="i-box-content">
          <List divided size="big">
            {subMailingLists.map(list => (
              <ListItem className="mailing" key={list.id}>
                <ListContent>
                  <Checkbox
                    label={list.name}
                    value={list.id}
                    onChange={handleSelectSubscribed}
                    checked={selectedSubscribed.includes(list.id)}
                  />
                </ListContent>
              </ListItem>
            ))}
            <ListItem>
              <Button
                icon
                labelPosition="left"
                className="unsubscribe-btn"
                onClick={() => unsubscribeList(selectedSubscribed)}
                disabled={selectedSubscribed.length === 0}
              >
                <Icon name="minus" />
                <Translate>Unsubscribe</Translate>
              </Button>
            </ListItem>
          </List>
        </div>
      </div>

      {/* Not Subscribed Lists Section */}
      <div className="i-box" style={{marginTop: '15px'}}>
        <div className="i-box-header">
          <div className="i-box-title">
            <Translate>Not Subscribed Lists</Translate>
          </div>
        </div>
        <div className="i-box-content">
          <List divided size="big">
            {notSubMailingLists.map(list => (
              <ListItem className="mailing" key={list.id}>
                <ListContent>
                  <Checkbox
                    label={list.name}
                    value={list.id}
                    onChange={handleSelectNotSubscribed}
                    checked={selectedNotSubscribed.includes(list.id)}
                  />
                </ListContent>
              </ListItem>
            ))}
            <ListItem>
              <Button
                icon
                labelPosition="left"
                primary
                className="subscribe-btn"
                onClick={() => subscribeList(selectedNotSubscribed)}
                disabled={selectedNotSubscribed.length === 0}
              >
                <Icon name="plus" />
                <Translate>Subscribe</Translate>
              </Button>
            </ListItem>
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
