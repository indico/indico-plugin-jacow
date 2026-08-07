// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import mailingListSubscriptionURL from 'indico-url:plugin_jacow.user_mailing_lists_subscription';

import PropTypes from 'prop-types';
import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import {ListItem, ListContent, List, Checkbox} from 'semantic-ui-react';

import {indicoAxios, handleAxiosError} from 'indico/utils/axios';

import './mailing_lists.module.scss';

function MailingLists({mailingLists, userId}) {
  const [listGroups, setListGroups] = useState(mailingLists);
  const [listsLoadingRequests, setListsLoadingRequests] = useState(new Set());

  const lists = listGroups.flatMap(group => group.lists);
  const userIdArgs = userId !== null ? {user_id: userId} : {};

  const subscribeList = async listId => {
    await indicoAxios.put(mailingListSubscriptionURL({...userIdArgs, list_id: listId}));
  };

  const unsubscribeList = async listId => {
    await indicoAxios.delete(mailingListSubscriptionURL({...userIdArgs, list_id: listId}));
  };

  const handleToggle = async (ev, {value}) => {
    if (listsLoadingRequests.has(value)) {
      return;
    }

    setListsLoadingRequests(prev => new Set(prev).add(value));

    const targetList = lists.find(list => list.id === value);
    const newSubscriptionStatus = !targetList.subscribed;

    setListGroups(prevListGroups =>
      prevListGroups.map(group => ({
        ...group,
        lists: group.lists.map(list =>
          list.id === value ? {...list, subscribed: newSubscriptionStatus} : list
        ),
      }))
    );

    try {
      if (newSubscriptionStatus) {
        await subscribeList(value);
      } else {
        await unsubscribeList(value);
      }
    } catch (e) {
      handleAxiosError(e);
      setListGroups(prevListGroups =>
        prevListGroups.map(group => ({
          ...group,
          lists: group.lists.map(list =>
            list.id === value ? {...list, subscribed: !newSubscriptionStatus} : list
          ),
        }))
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
    <div className="i-box-group vert" style={{marginTop: '15px'}}>
      {listGroups.map(({key, title, restricted, has_access: hasAccess, lists: groupLists}) => (
        <div className="i-box" key={key}>
          <div className="i-box-header">
            <div className="i-box-title">
              {restricted && <i className="lock icon" title="These mailing lists are restricted" />}
              {title}
            </div>
          </div>
          <div className="i-box-content">
            {restricted && (
              <div className="highlight-message-box">
                <div className="message-box-content">
                  <div className="message-text">
                    The lists in this folder are restricted.
                    <br />
                    {hasAccess ? (
                      <>
                        As an Indico admin (or JACoW repository manager) you can manage the
                        subscription anyway.
                      </>
                    ) : (
                      <>Your subscription to these lists cannot be managed via Indico.</>
                    )}
                  </div>
                </div>
              </div>
            )}
            <List divided relaxed size="big">
              {groupLists.map(list => (
                <ListItem styleName="mailing" key={list.id}>
                  <ListContent>{list.name}</ListContent>
                  <ListContent>
                    <Checkbox
                      toggle
                      value={list.id}
                      onChange={handleToggle}
                      disabled={listsLoadingRequests.has(list.id) || !hasAccess}
                      checked={list.subscribed}
                    />
                  </ListContent>
                </ListItem>
              ))}
            </List>
          </div>
        </div>
      ))}
    </div>
  );
}

MailingLists.propTypes = {
  mailingLists: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      restricted: PropTypes.bool.isRequired,
      has_access: PropTypes.bool.isRequired,
      lists: PropTypes.arrayOf(
        PropTypes.shape({
          id: PropTypes.number.isRequired,
          name: PropTypes.string.isRequired,
          subscribed: PropTypes.bool.isRequired,
        })
      ).isRequired,
    })
  ).isRequired,
  userId: PropTypes.number,
};

customElements.define(
  'ind-jacow-mailing-lists',
  class extends HTMLElement {
    connectedCallback() {
      const userId = JSON.parse(this.getAttribute('user-id'));
      const lists = JSON.parse(this.getAttribute('lists'));

      ReactDOM.render(<MailingLists mailingLists={lists} userId={userId} />, this);
    }
  }
);
