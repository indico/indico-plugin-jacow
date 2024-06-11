// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import uploadManagersFileURL from 'indico-url:plugin_jacow.peer_review_managers_import'

import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Button, Message, MessageHeader, MessageList, MessageItem, Icon} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import {FinalSingleFileManager} from 'indico/react/components';
import {FinalModalForm} from 'indico/react/forms/final-form';

import './PeerReviewManagerFileInput.module.scss';

const PeerReviewManagersFileInput = ({eventId}) => {
    return (
        <div>
            <Message info icon styleName="message-icon">
                <Icon name='lightbulb'/>
                <Message.Content>
                    <MessageHeader>
                        <Translate>Upload a CSV (comma-separated values)</Translate>
                    </MessageHeader>
                    <p>The file most have exactly 6 columns in the following order:</p>
                    <MessageList>
                        <MessageItem>{Translate.string('First Name')}</MessageItem>
                        <MessageItem>{Translate.string('Last Name')}</MessageItem>
                        <MessageItem>{Translate.string('Affiliation')}</MessageItem>
                        <MessageItem>{Translate.string('Position')}</MessageItem>
                        <MessageItem>{Translate.string('Phone Number')}</MessageItem>
                        <MessageItem>{Translate.string('E-mail')}</MessageItem>
                    </MessageList>
                    <p>The fields "First Name", "Last Name" and "E-mail" are mandatory.</p>
                    <p>Users will be matched with existing Indico identities through their e-mail.</p>
                    </Message.Content>
            </Message>
            <FinalSingleFileManager
                name="file"
                validExtensions={['csv']}
                uploadURL={uploadManagersFileURL({event_id: eventId})}
            />
        </div>
    );
}

export default function PeerReviewManagersFileField ({onClose, fieldId, eventId}) {
    
    return (
        <FinalModalForm
            id="peer-review-managers-file"
            size="tiny"
            onClose={onClose}
            onSubmit={{}}
            header={`Import ${fieldId.replace('_', ' ')}`}
        >
            <PeerReviewManagersFileInput eventId={eventId}/>
        </FinalModalForm>
    )
}

export function PeerReviewManagersFileButton ({fieldId, eventId}) {
    const [fileImportVisible, setFileImportVisible] = useState(false);

    if (fieldId !== 'judges' && fieldId !== 'content_reviewers'){
        return null
    }

    return (
        <>
            <Button 
                icon='download'
                as='div'
                title={Translate.string('Export (CSV)')}
                onClick={{}}
            />
            <Button 
                icon='upload'
                as='div'
                title={Translate.string('Import (CSV)')}
                onClick={() => setFileImportVisible(true)}
            />
            {fileImportVisible && (
                <PeerReviewManagersFileField 
                    onClose={() => setFileImportVisible(false)}
                    fieldId={fieldId}
                    eventId={eventId}
                />
            )}
        </>
    );
}
