// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

// import downloadManagersFileURL from 'indico-url:plugin_jacow.peer_review_managers_export'
import uploadManagersFileURL from 'indico-url:plugin_jacow.peer_review_managers_import'

import PropTypes from 'prop-types';
import React, {useCallback, useState} from 'react';
import {useDropzone} from 'react-dropzone';
import {Button, Message, MessageHeader, MessageList, 
    MessageItem, Icon, Loader, Segment, Dimmer} from 'semantic-ui-react';
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
    setUnknownEmails,
    setUserIdentifiers,
    setLoading,
    eventId,
}) => {
    const [file, setFile] = useState();

    const markTouched = () => {
        onFocus();
        onBlur();
    };

    async function getUserList(file, eventId) {
        const headers = {'content-type': 'multipart/form-data'}
        let response;
        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            response = await indicoAxios.post(uploadManagersFileURL({event_id: eventId}), formData, {headers});
            if (response.data.unknown_emails.length > 0) {
                setUnknownEmails(response.data.unknown_emails)
            }
            setUserIdentifiers(response.data.identifiers)
            return true;
        } catch (e) {
            handleSubmitError(e);
            return false;
        } finally {
            setLoading(false);
        }
    }

    const onDropAccepted = useCallback(async ([acceptedFile]) => {
        Object.assign(acceptedFile, {filename: acceptedFile.name});
        const isSuccess = await getUserList(acceptedFile, eventId);
        if(isSuccess){
            setFile(acceptedFile);
            onChange(acceptedFile);
        }
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
    const [unknownEmails, setUnknownEmails] = useState([])
    const [userIdentifiers, setUserIdentifiers] = useState([])
    const [loading, setLoading] = useState(false)

    const handleSubmit = async () => {
        onChange(userIdentifiers)
        onClose();
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
                <Message info icon>
                    <Icon name='lightbulb'/>
                    <Message.Content>
                        <MessageHeader>
                            <Translate>Upload a CSV (comma-separated values)</Translate>
                        </MessageHeader>
                        <p></p>
                        <MessageList>
                            <MessageItem>
                                {Translate.string('The file most have at least one column labeled "Email"')}
                            </MessageItem>
                            <MessageItem>
                                {Translate.string('Any other fields like "First Name" and "Last Name" are acceptable but not needed.')}
                            </MessageItem>
                        </MessageList>
                        <p>Users will be matched with existing Indico identities through their e-mail.</p>
                    </Message.Content>
                </Message>
                {loading && (
                    <Dimmer active inverted>
                        <Loader inline/>
                    </Dimmer>
                )}
                {unknownEmails.length > 0 && (
                    <Message icon color="yellow">
                        <Icon name="warning sign"/>
                        <Message.Content>
                            <MessageHeader>
                                <Translate>The following emails are not registered and won't be imported:</Translate>
                            </MessageHeader>
                            <MessageList>
                                {unknownEmails.map((e, i) => {
                                    return <MessageItem key={i}>{e}</MessageItem>
                                })}
                            </MessageList>
                        </Message.Content>
                    </Message>
                )}
                <Field
                    name='file'
                    render={({input: {onChange: setDummyValue}}) => (
                        <FinalField   
                            name='file'
                            validExtensions={['csv']}
                            component={PeerReviewManagersFileInput}
                            setValidationError={setDummyValue}
                            setUnknownEmails={setUnknownEmails}
                            setUserIdentifiers={setUserIdentifiers}
                            setLoading={setLoading}
                            eventId={eventId}
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

    async function downloadCSVFile() {
        await indicoAxios.post(downloadManagersFileURL({event_id: eventId}))
    }

    return (
        <>
            <Button 
                icon='download'
                as='div'
                title={Translate.string('Export (CSV)')}
                // TODO: Create an endpoint for managers data exporting
                // onClick={downloadCSVFile()}
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
