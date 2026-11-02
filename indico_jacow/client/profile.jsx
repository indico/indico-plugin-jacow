// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2026 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import affiliationRorURL from 'indico-url:plugin_jacow.affiliation_ror';
import profileAPIURL from 'indico-url:plugin_jacow.user_jacow_profile_api';
import orcidURL from 'indico-url:plugin_jacow.user_jacow_profile_orcid';
import orcidConnectURL from 'indico-url:plugin_jacow.user_jacow_profile_orcid_connect';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import {Form as FinalForm, FormSpy, useForm} from 'react-final-form';
import {Button, Confirm, Form, Header, Label, Message, Segment} from 'semantic-ui-react';

import {
  FinalCheckbox,
  FinalDropdown,
  FinalField,
  FinalInput,
  FinalSubmitButton,
} from 'indico/react/forms';
import {FinalModalForm, handleSubmitError} from 'indico/react/forms/final-form';
import {Param} from 'indico/react/i18n';
import {handleAxiosError, indicoAxios} from 'indico/utils/axios';
import {camelizeKeys} from 'indico/utils/case';

import {Translate} from './i18n';
import {MultipleAffiliationsField, affiliationToValue} from './MultipleAffiliationsSelector';

const ROR_ID_RE = /^(?:https?:\/\/(?:www\.)?ror\.org\/)?(0[0-9a-hjkmnp-tv-z]{6}\d{2})$/i;

const normalizeRorId = value => {
  const match = typeof value === 'string' && value.trim().match(ROR_ID_RE);
  return match ? match[1].toLowerCase() : null;
};

// Affiliations coming from the profile API already contain the ROR ID; for ones that were
// just added from the affiliation search we look it up in the (camelized) affiliation metadata.
const getRorId = (affiliation, rorMetaKey) => {
  if (affiliation.meta.rorId !== undefined) {
    return affiliation.meta.rorId;
  }
  if (!rorMetaKey) {
    return null;
  }
  const lookup = parts =>
    parts.reduce((obj, part) => (_.isPlainObject(obj) ? obj[part] : null), affiliation.meta.meta);
  const parts = rorMetaKey.split('.');
  return normalizeRorId(lookup(parts) ?? lookup(parts.map(_.camelCase)));
};

const formatInitials = (firstName, hyphenated) =>
  firstName
    .split(/\s+/)
    .map(name =>
      name
        .split('-')
        .filter(part => part)
        .map(part => `${part[0].toUpperCase()}.`)
        .join('-')
    )
    .filter(initials => initials)
    .join(hyphenated ? '-' : ' ');

const formatAuthorName = (firstName, lastName, initialsFormat, fullFirstName) => {
  firstName = firstName.trim();
  const first = fullFirstName
    ? firstName.split(/\s+/).join(' ')
    : formatInitials(firstName, initialsFormat === 'hyphenated');
  return `${first} ${lastName.trim()}`.trim();
};

function SetRorIdButton({affiliation, onSaved}) {
  const [modalOpen, setModalOpen] = useState(false);

  const onSubmit = async ({ror_id: rorId}) => {
    let resp;
    try {
      resp = await indicoAxios.put(affiliationRorURL({affiliation_id: affiliation.id}), {
        ror_id: rorId,
      });
    } catch (e) {
      return handleSubmitError(e);
    }
    onSaved(camelizeKeys(resp.data));
    setModalOpen(false);
  };

  return (
    <>
      <a onClick={() => setModalOpen(true)}>
        <Translate>Set ROR ID</Translate>
      </a>
      {modalOpen && (
        <FinalModalForm
          id="set-affiliation-ror"
          size="tiny"
          onClose={() => setModalOpen(false)}
          onSubmit={onSubmit}
          header={Translate.string('Set ROR ID of "{name}"', {name: affiliation.meta.name})}
          submitLabel={Translate.string('Save')}
        >
          <Message info>
            <Translate>
              This affiliation is not linked to the{' '}
              <Param
                name="ror"
                wrapper={<a href="https://ror.org/" target="_blank" rel="noopener noreferrer" />}
              >
                ROR registry
              </Param>
              . Look it up there and paste its ROR ID or URL below. This changes the affiliation for
              everyone using it.
            </Translate>
          </Message>
          <FinalInput
            name="ror_id"
            label={Translate.string('ROR ID')}
            placeholder="https://ror.org/01ggx4157"
            validate={v => (normalizeRorId(v) ? undefined : Translate.string('Invalid ROR ID'))}
            required
          />
        </FinalModalForm>
      )}
    </>
  );
}

SetRorIdButton.propTypes = {
  affiliation: PropTypes.object.isRequired,
  onSaved: PropTypes.func.isRequired,
};

function RorInfo({affiliation, index, rorMetaKey, canManageAffiliations}) {
  const form = useForm();
  const rorId = getRorId(affiliation, rorMetaKey);

  const onSaved = data => {
    const affiliations = form.getState().values.affiliations.slice();
    affiliations[index] = affiliationToValue(data);
    form.change('affiliations', affiliations);
  };

  if (rorId) {
    return (
      <Label
        as="a"
        href={`https://ror.org/${rorId}`}
        target="_blank"
        rel="noopener noreferrer"
        basic
        size="small"
        title={Translate.string('Open in the ROR registry')}
        style={{marginLeft: '1em', whiteSpace: 'nowrap'}}
      >
        ROR <Label.Detail>{rorId}</Label.Detail>
      </Label>
    );
  }
  return (
    <span style={{marginLeft: '1em', whiteSpace: 'nowrap'}}>
      <Label
        basic
        color="orange"
        size="small"
        content={Translate.string('No ROR ID')}
        title={Translate.string(
          'This affiliation is not linked to the ROR registry, e.g. because it was added manually.'
        )}
      />{' '}
      {canManageAffiliations && <SetRorIdButton affiliation={affiliation} onSaved={onSaved} />}
    </span>
  );
}

RorInfo.propTypes = {
  affiliation: PropTypes.object.isRequired,
  index: PropTypes.number.isRequired,
  rorMetaKey: PropTypes.string.isRequired,
  canManageAffiliations: PropTypes.bool.isRequired,
};

const ORCIDLogo = () => (
  <span
    aria-hidden="true"
    style={{
      display: 'inline-block',
      width: '1.4em',
      height: '1.4em',
      lineHeight: '1.4em',
      borderRadius: '50%',
      background: '#a6ce39',
      color: 'white',
      fontWeight: 'bold',
      fontSize: '0.85em',
      textAlign: 'center',
      marginRight: '0.5em',
    }}
  >
    iD
  </span>
);

function ORCIDConnection({profile, onChange, userIdArgs, canConnect, configured}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const disconnect = async () => {
    setConfirmOpen(false);
    setDisconnecting(true);
    let resp;
    try {
      resp = await indicoAxios.delete(orcidURL(userIdArgs));
    } catch (e) {
      handleAxiosError(e);
      return;
    } finally {
      setDisconnecting(false);
    }
    onChange(camelizeKeys(resp.data));
  };

  let content;
  if (profile.orcid) {
    content = (
      <>
        <p>
          <ORCIDLogo />
          <a href={profile.orcidUrl} target="_blank" rel="noopener noreferrer">
            {profile.orcidUrl}
          </a>
        </p>
        {profile.orcidConnectedDt && (
          <p>
            <Translate>
              Connected on{' '}
              <Param name="date" value={new Date(profile.orcidConnectedDt).toLocaleDateString()} />{' '}
              by signing in at ORCID.
            </Translate>
          </p>
        )}
        <Button
          type="button"
          size="small"
          content={Translate.string('Disconnect')}
          onClick={() => setConfirmOpen(true)}
          loading={disconnecting}
          disabled={disconnecting}
        />
        <Confirm
          open={confirmOpen}
          header={Translate.string('Disconnect ORCID iD')}
          content={Translate.string(
            'Events may require a connected ORCID iD to add you as an author. You can connect it again at any time.'
          )}
          confirmButton={Translate.string('Disconnect')}
          cancelButton={Translate.string('Cancel')}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={disconnect}
          size="tiny"
        />
      </>
    );
  } else if (!configured) {
    content = <p>{Translate.string('Connecting an ORCID iD is currently not available.')}</p>;
  } else if (!canConnect) {
    content = (
      <p>
        {Translate.string(
          'No ORCID iD connected. Only the user themselves can connect their ORCID iD, since they need to sign in at ORCID.'
        )}
      </p>
    );
  } else {
    content = (
      <>
        <p>
          <Translate>
            Connect your ORCID iD by signing in at ORCID. This proves that the iD is yours; it is
            then included with your contributions in all events.
          </Translate>
        </p>
        <Button as="a" href={orcidConnectURL(userIdArgs)} basic>
          <ORCIDLogo />
          <Translate>Connect your ORCID iD</Translate>
        </Button>
      </>
    );
  }

  return (
    <Segment>
      <Header as="h4" content="ORCID" />
      {content}
    </Segment>
  );
}

ORCIDConnection.propTypes = {
  profile: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  userIdArgs: PropTypes.object.isRequired,
  canConnect: PropTypes.bool.isRequired,
  configured: PropTypes.bool.isRequired,
};

const profileToFormValues = profile => ({
  affiliations: profile.affiliations.map(affiliationToValue),
  initials_format: profile.initialsFormat,
  full_first_name: profile.fullFirstName,
});

function JACoWProfile({
  userId,
  firstName,
  lastName,
  profile: initialProfile,
  initialsFormats,
  rorMetaKey,
  canManageAffiliations,
  orcidConfigured,
  canConnectOrcid,
}) {
  const [profile, setProfile] = useState(initialProfile);
  const userIdArgs = userId !== null ? {user_id: userId} : {};

  const handleSubmit = async data => {
    let resp;
    try {
      resp = await indicoAxios.put(profileAPIURL(userIdArgs), {
        affiliation_ids: data.affiliations.map(x => x.id),
        initials_format: data.initials_format,
        full_first_name: data.full_first_name,
      });
    } catch (e) {
      return handleSubmitError(e, {affiliation_ids: 'affiliations'});
    }
    setProfile(camelizeKeys(resp.data));
  };

  return (
    <>
      <Message info style={{marginTop: '15px'}}>
        <Translate>
          The information on this page is stored on your user profile and is used for all your
          contributions in all JACoW events.
        </Translate>
      </Message>
      <ORCIDConnection
        profile={profile}
        onChange={newProfile => setProfile(prev => ({...prev, ...newProfile}))}
        userIdArgs={userIdArgs}
        canConnect={canConnectOrcid}
        configured={orcidConfigured}
      />
      <FinalForm
        onSubmit={handleSubmit}
        initialValues={profileToFormValues(profile)}
        initialValuesEqual={_.isEqual}
        subscription={{}}
      >
        {fprops => (
          <Form onSubmit={fprops.handleSubmit}>
            <FinalField
              name="affiliations"
              label={Translate.string('Affiliations')}
              component={MultipleAffiliationsField}
              currentAffiliations={profile.affiliations}
              isEqual={_.isEqual}
              renderAffiliationExtra={(affiliation, index) => (
                <RorInfo
                  affiliation={affiliation}
                  index={index}
                  rorMetaKey={rorMetaKey}
                  canManageAffiliations={canManageAffiliations}
                />
              )}
              description={Translate.string(
                'Your affiliations in order of importance. They are suggested when you are added as an author, and the first one is also used as your main Indico affiliation.'
              )}
            />
            <Segment>
              <FinalDropdown
                name="initials_format"
                label={Translate.string('Initials of multiple first names')}
                options={initialsFormats.map(({value, title}) => ({
                  key: value,
                  value,
                  text: title,
                }))}
                selection
                required
              />
              <FinalCheckbox
                name="full_first_name"
                label={Translate.string(
                  'My name is natively written in a non-Latin alphabet: always show my full first name instead of initials'
                )}
              />
              <FormSpy subscription={{values: true}}>
                {({values}) => (
                  <p>
                    <Translate>Your name in author lists:</Translate>{' '}
                    <strong>
                      {formatAuthorName(
                        firstName,
                        lastName,
                        values.initials_format,
                        values.full_first_name
                      )}
                    </strong>
                  </p>
                )}
              </FormSpy>
            </Segment>
            <FinalSubmitButton label={Translate.string('Save changes')} disabledUntilChange />
            <FormSpy subscription={{submitError: true}}>
              {({submitError}) =>
                submitError ? <Message error visible content={submitError} /> : null
              }
            </FormSpy>
            <FormSpy subscription={{submitSucceeded: true, dirtySinceLastSubmit: true}}>
              {({submitSucceeded, dirtySinceLastSubmit}) =>
                submitSucceeded && !dirtySinceLastSubmit ? (
                  <Message
                    success
                    visible
                    content={Translate.string('Your JACoW profile has been saved.')}
                  />
                ) : null
              }
            </FormSpy>
          </Form>
        )}
      </FinalForm>
    </>
  );
}

JACoWProfile.propTypes = {
  userId: PropTypes.number,
  firstName: PropTypes.string.isRequired,
  lastName: PropTypes.string.isRequired,
  profile: PropTypes.shape({
    orcid: PropTypes.string,
    orcidUrl: PropTypes.string,
    orcidConnectedDt: PropTypes.string,
    affiliations: PropTypes.array.isRequired,
    initialsFormat: PropTypes.string.isRequired,
    fullFirstName: PropTypes.bool.isRequired,
  }).isRequired,
  initialsFormats: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
    })
  ).isRequired,
  rorMetaKey: PropTypes.string.isRequired,
  canManageAffiliations: PropTypes.bool.isRequired,
  orcidConfigured: PropTypes.bool.isRequired,
  canConnectOrcid: PropTypes.bool.isRequired,
};

JACoWProfile.defaultProps = {
  userId: null,
};

customElements.define(
  'ind-jacow-profile',
  class extends HTMLElement {
    connectedCallback() {
      const attr = name => JSON.parse(this.getAttribute(name));
      ReactDOM.render(
        <JACoWProfile
          userId={attr('user-id')}
          firstName={attr('first-name')}
          lastName={attr('last-name')}
          profile={camelizeKeys(attr('profile'))}
          initialsFormats={attr('initials-formats')}
          rorMetaKey={attr('ror-meta-key')}
          canManageAffiliations={attr('can-manage-affiliations')}
          orcidConfigured={attr('orcid-configured')}
          canConnectOrcid={attr('can-connect-orcid')}
        />,
        this
      );
    }
  }
);
