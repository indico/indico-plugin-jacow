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
import {useState} from 'react';
import ReactDOM from 'react-dom';
import {ListItem, ListContent, List, Checkbox} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

import './MailingList.module.scss';

export function MailingList({mailingLists}) {
  const [lists, setLists] = useState(mailingLists.lists);
  const [listsLoadingRequests, setListsLoadingRequests] = useState(new Set());

  const subscribeList = async list => {
    await indicoAxios.post(mailingListSubscribeURL(), list);
  };

  const unsubscribeList = async list => {
    await indicoAxios.post(mailingListUnsubscribeURL(), list);
  };

  const handleToggle = async (ev, {value}) => {
    if (listsLoadingRequests.has(value)) return;
    
    setListsLoadingRequests(prev => new Set(prev).add(value));

    const targetList = lists.find(list => list.id === value);
    const newSubscriptionStatus = !targetList.subscribed;
    
    setLists(prevLists =>
      prevLists.map(list =>
        list.id === value ? { ...list, subscribed: newSubscriptionStatus } : list
      )
    );

    try {
      if (newSubscriptionStatus) {
        await subscribeList({list_id: value});
      } else {
        await unsubscribeList({list_id: value});
      }
    } catch (e) {
      handleAxiosError(e);
      setLists(prevLists =>
        prevLists.map(list =>
          list.id === value ? { ...list, subscribed: !newSubscriptionStatus } : list
        )
      );
    } finally {
      setListsLoadingRequests(prev => {
        const newSet = new Set(prev);
        newSet.delete(value);
        return newSet;
      });
    }
  };

  return (
    <div style={{marginTop: '15px'}}>
      {/* Subscribed Lists Section */}
      <div className="i-box">
        <div className="i-box-header">
          <div className="i-box-title">
            <Translate>Mailing Lists</Translate>
          </div>
        </div>
        <div className="i-box-content">
          <List divided relaxed size="big">
            {lists.map(list => (
              <ListItem styleName="mailing" key={list.id}>
                <ListContent>{list.name}</ListContent>
                <ListContent>
                  <Checkbox
                    toggle
                    value={list.id}
                    onChange={handleToggle}
                    disabled={listsLoadingRequests.has(list.id)}
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
