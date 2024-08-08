// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import uploadManagersFileURL from 'indico-url:plugin_jacow.peer_review_managers_import'

import PropTypes from 'prop-types';
import React, {useCallback, useState} from 'react';
import {useDropzone} from 'react-dropzone';
import {Button, Message, MessageHeader, MessageList, MessageItem, Icon} from 'semantic-ui-react';
import {Field} from 'react-final-form';

import {FinalField, handleSubmitError} from 'indico/react/forms';
import {Translate} from 'indico/react/i18n';

import {SingleFileArea} from 'indico/react/components/files/FileArea';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {indicoAxios} from 'indico/utils/axios';

import './PeerReviewManagerFileInput.module.scss';

const PeerReviewManagersFileInput = ({
    onFocus,
    onBlur,
    onChange,
    validExtensions,
}) => {
    const [file, setFile] = useState();

    const markTouched = () => {
        onFocus();
        onBlur();
    };

    const onDropAccepted = useCallback(([acceptedFile]) => {
        Object.assign(acceptedFile, {filename: acceptedFile.name});
        setFile(acceptedFile);
        onChange(acceptedFile);
    }, [file, setFile, onChange]);

    const dropzone = useDropzone({
        onDragEnter: markTouched,
        onFileDialogCancel: markTouched,
        onDrop: markTouched,
        onDropAccepted,
        accept: validExtensions ? validExtensions.map(ext => `.${ext}`) : null,
        multiple: false,
        noClick: true,
        noKeyboard: true,
    });

    return <SingleFileArea dropzone={dropzone} file={file} />;
};


export default function PeerReviewManagersFileField ({onClose, fieldId, eventId, onChange}) {
    const handleSubmit = async ({file}) => {
        const headers = {'content-type': 'multipart/form-data'}
        let identifiers;
        try {
            const formData = new FormData();
            formData.append('file', file);
            identifiers = await indicoAxios.post(uploadManagersFileURL({event_id: eventId}), formData, {headers});
            // TODO: Flash success or error message
            onChange(identifiers.data.identifiers)
            onClose();
        } catch (e) {
            return handleSubmitError(e);
        }
    }

    return (
        <FinalModalForm
            id="peer-review-managers-file"
            size="small"
            onClose={onClose}
            onSubmit={handleSubmit}
            header={`Import ${fieldId.replace('_', ' ')}`}
            submitLabel={Translate.string('Import')}
        >
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
                <Field
                    name='file'
                    render={({input: {onChange: setDummyValue}}) => (
                        <FinalField   
                            name='file'
                            validExtensions={['csv']}
                            component={PeerReviewManagersFileInput}
                            setValidationError={setDummyValue}
                        />
                    )}
                />
        </FinalModalForm>
    )
}

export function PeerReviewManagersFileButton ({fieldId, eventId, onChange}) {
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
                // TODO: Create an endpoint for managers data exporting
                onClick={()=>{}}
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
                    onChange={onChange}
                />
            )}
        </>
    );
}
