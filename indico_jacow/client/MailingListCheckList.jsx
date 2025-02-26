// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import getMailingListsURL from 'indico-url:plugin_jacow.mailing_lists';

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
                  <Button icon labelPosition="left" className="subscribe-btn">
                    <Icon name="minus" />
                    <Translate>Unsubscribe</Translate>
                  </Button>
                ) : (
                  <Button icon labelPosition="left" primary className="subscribe-btn">
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
