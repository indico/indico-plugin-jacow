// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import uploadManagersFileURL from 'indico-url:plugin_jacow.peer_review_csv_import';

import PropTypes from 'prop-types';
import React, {useCallback, useContext, useState} from 'react';
import {useDropzone} from 'react-dropzone';
import {Field} from 'react-final-form';
import {
  Button,
  Message,
  MessageHeader,
  MessageList,
  MessageItem,
  Icon,
  Loader,
  Dimmer,
} from 'semantic-ui-react';

import {SingleFileArea} from 'indico/react/components/files/FileArea';
import {FormContext, FinalField, handleSubmitError} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import './PeerReviewManagerFileInput.module.scss';

const PeerReviewManagersFileInput = ({
  setValidationError,
  setUnknownEmails,
  setUserIdentifiers,
  setLoading,
  eventId,
}) => {
  const [uploadedFile, setFile] = useState();
  const validExtensions = ['csv'];

  const userList = useCallback(
    async file => {
      const headers = {'content-type': 'multipart/form-data'};
      let response;
      setLoading(true);
      try {
        const formData = new FormData();
        formData.append('file', file);
        response = await indicoAxios.post(uploadManagersFileURL({event_id: eventId}), formData, {
          headers,
        });
        if (response.data.unknown_emails.length > 0) {
          setUnknownEmails(response.data.unknown_emails);
        }
        setUserIdentifiers(response.data.identifiers);
        return true;
      } catch (e) {
        handleSubmitError(e);
        return false;
      } finally {
        setLoading(false);
      }
    },
    [eventId, setLoading, setUnknownEmails, setUserIdentifiers]
  );

  const onDropAccepted = useCallback(
    async ([acceptedFile]) => {
      acceptedFile.filename = acceptedFile.name;
      const isSuccess = await userList(acceptedFile);
      if (isSuccess) {
        setFile(acceptedFile);
        setValidationError(acceptedFile);
      }
    },
    [userList, setValidationError]
  );

  const dropzone = useDropzone({
    onDropAccepted,
    accept: validExtensions ? validExtensions.map(ext => `.${ext}`) : null,
    multiple: false,
    noClick: true,
    noKeyboard: true,
  });

  return <SingleFileArea dropzone={dropzone} file={uploadedFile} />;
};
PeerReviewManagersFileInput.propTypes = {
  setValidationError: PropTypes.func.isRequired,
  setUnknownEmails: PropTypes.func.isRequired,
  setUserIdentifiers: PropTypes.func.isRequired,
  setLoading: PropTypes.func.isRequired,
  eventId: PropTypes.number.isRequired,
};

function PeerReviewManagersFileField({onClose, eventId, onChange}) {
  const [unknownEmails, setUnknownEmails] = useState([]);
  const [userIdentifiers, setUserIdentifiers] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    onChange(userIdentifiers);
    onClose();
  };

  return (
    <FinalModalForm
      id="peer-review-managers-file"
      size="small"
      onClose={onClose}
      onSubmit={handleSubmit}
      header={Translate.string('Import from CSV')}
      submitLabel={Translate.string('Import')}
    >
      <Message info icon>
        <Icon name="lightbulb" />
        <Message.Content>
          <MessageHeader>
            <Translate>Upload a CSV (comma-separated values)</Translate>
          </MessageHeader>
          <MessageList>
            <MessageItem>
              <Translate>The file must have at least one column labeled "Email".</Translate>
            </MessageItem>
            <MessageItem>
              <Translate>
                Any other fields like "First Name" and "Last Name" are acceptable but not needed.
              </Translate>
            </MessageItem>
          </MessageList>
          <p>Users will be matched with existing Indico identities through their e-mail.</p>
        </Message.Content>
      </Message>
      {loading && (
        <Dimmer active inverted>
          <Loader inline />
        </Dimmer>
      )}
      {unknownEmails.length > 0 && (
        <Message icon color="yellow">
          <Icon name="warning sign" />
          <Message.Content>
            <MessageHeader>
              <Translate>The following emails are not registered and won't be imported:</Translate>
            </MessageHeader>
            <MessageList>
              {unknownEmails.map(e => (
                <MessageItem key={e}>{e}</MessageItem>
              ))}
            </MessageList>
          </Message.Content>
        </Message>
      )}
      <Field
        name="file"
        render={({input: {onChange: setDummyValue}}) => (
          <FinalField
            name="file"
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
  );
}
PeerReviewManagersFileField.propTypes = {
  onClose: PropTypes.func.isRequired,
  eventId: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
};

export function PeerReviewManagersFileButton({entries, eventId, onChange}) {
  const formContext = useContext(FormContext);
  const [fileImportVisible, setFileImportVisible] = useState(false);

  const downloadCSV = () => {
    const headers = ['First Name', 'Last Name', 'Email', 'Phone Number'];
    const rows = entries.map(e => [e.firstName, e.lastName, e.email, e.phone || 'N/A']);

    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += `${headers.join(',')}\n`;
    rows.forEach(row => {
      csvContent += `${row.join(',')}\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'peer_review_management.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (
    !formContext ||
    formContext[0] !== 'PaperTeamsForm' ||
    !['judges', 'content_reviewers'].includes(formContext[1])
  ) {
    return null;
  }

  return (
    <>
      <Button
        icon="download"
        as="div"
        onClick={downloadCSV}
        title={Translate.string('Export (CSV)')}
      />
      <Button
        icon="upload"
        as="div"
        title={Translate.string('Import (CSV)')}
        onClick={() => setFileImportVisible(true)}
      />
      {fileImportVisible && (
        <PeerReviewManagersFileField
          onClose={() => setFileImportVisible(false)}
          eventId={eventId}
          onChange={onChange}
        />
      )}
    </>
  );
}
PeerReviewManagersFileButton.propTypes = {
  entries: PropTypes.arrayOf(PropTypes.object).isRequired,
  eventId: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
};
