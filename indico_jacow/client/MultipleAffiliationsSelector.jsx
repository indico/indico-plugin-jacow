// This file is part of the JACoW plugin.
// Copyright (C) 2014 - 2023 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import searchAffiliationURL from 'indico-url:users.api_affiliations';

import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {useFormState} from 'react-final-form';
import {Dropdown, Icon, IconGroup, Header} from 'semantic-ui-react';

import {FinalField, FormFieldAdapter} from 'indico/react/forms';
import {FinalModalForm} from 'indico/react/forms/final-form';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';
import {camelizeKeys} from 'indico/utils/case';
import {makeAsyncDebounce} from 'indico/utils/debounce';

import {Translate} from './i18n';

const debounce = makeAsyncDebounce(250);

const AffiliationsFieldAdapter = ({options, ...rest}) => (
  <FormFieldAdapter
    options={options}
    {...rest}
    as={Dropdown}
    clearable
    multiple
    search
    selection
    fluid
    undefinedValue={null}
    selectOnBlur={false}
    selectOnNavigation={false}
    getValue={(__, {value}) =>
      options
        .filter(opt => value.includes(opt.value))
        .map(opt => ({
          id: opt.value,
          text: opt.text,
          meta: opt.meta,
        }))
    }
  />
);

AffiliationsFieldAdapter.propTypes = {
  options: PropTypes.array.isRequired,
};

const FinalMultipleAffiliationField = () => {
  const formState = useFormState();
  const currentAffiliations = formState.values.jacowAffiliationsMeta || [];
  const selectedAffiliations = formState.values.affiliationsData.map(x => x.meta);
  const [_affiliationResults, setAffiliationResults] = useState(selectedAffiliations);
  const affiliationResults = [
    ...currentAffiliations,
    ..._affiliationResults.filter(x => !currentAffiliations.find(y => y.id === x.id)),
  ];

  const getSubheader = ({city, countryName}) => {
    if (city && countryName) {
      return `${city}, ${countryName}`;
    }
    return city || countryName;
  };

  const affiliationOptions = affiliationResults.map(res => ({
    key: res.id,
    value: res.id,
    text: res.name,
    meta: res,
    content: <Header style={{fontSize: 14}} content={res.name} subheader={getSubheader(res)} />,
  }));

  const searchAffiliationChange = async (evt, {searchQuery}) => {
    if (!searchQuery) {
      setAffiliationResults(selectedAffiliations);
      return;
    }
    let resp;
    try {
      resp = await debounce(() => indicoAxios.get(searchAffiliationURL({q: searchQuery})));
    } catch (error) {
      handleAxiosError(error);
      return;
    }
    setAffiliationResults([...selectedAffiliations, ...camelizeKeys(resp.data)]);
  };

  return (
    <FinalField
      name="affiliationsData"
      adapter={AffiliationsFieldAdapter}
      format={x => x.map(v => v.id)}
      parse={v => v}
      options={affiliationOptions}
      onSearchChange={searchAffiliationChange}
      placeholder={Translate.string('Select affiliations')}
      noResultsMessage={Translate.string('Search an affiliation')}
    />
  );
};

export default function MultipleAffiliationsSelector({
  persons,
  selected,
  onChange,
  onClose,
  modalOpen,
}) {
  const onSubmit = ({affiliationsData}) => {
    const value = persons[selected];
    value.jacowAffiliationsIds = affiliationsData.map(x => x.id);
    value.jacowAffiliationsMeta = affiliationsData.map(x => x.meta);
    value.affiliation = affiliationsData.map(x => x.text.trim()).join(', ');
    onChange(persons.map((v, idx) => (idx === selected ? value : v)));
    onClose();
  };

  return (
    modalOpen === 'jacow_affiliations' && (
      <FinalModalForm
        id="person-link-affiliations"
        size="tiny"
        onClose={onClose}
        onSubmit={onSubmit}
        header={Translate.string('Edit Affiliations')}
        submitLabel={Translate.string('Save')}
        initialValues={{
          affiliationsData:
            persons[selected].jacowAffiliationsMeta?.map(x => ({
              id: x.id,
              text: x.name,
              meta: x,
            })) || [],
        }}
      >
        <FinalMultipleAffiliationField />
      </FinalModalForm>
    )
  );
}

MultipleAffiliationsSelector.propTypes = {
  persons: PropTypes.array.isRequired,
  selected: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  modalOpen: PropTypes.string.isRequired,
};

export const MultipleAffiliationsButton = ({person, onEdit, disabled}) => (
  <IconGroup size="large">
    <Icon
      name="building"
      title={Translate.string('Edit affiliations')}
      color={person.jacowAffiliationsIds && person.jacowAffiliationsIds.length ? 'blue' : 'grey'}
      onClick={() => onEdit('jacow_affiliations')}
      disabled={disabled}
      link
    />
    {!person.jacowAffiliationsIds && (
      <Icon
        name="exclamation circle"
        title={Translate.string('No affiliations added')}
        color="red"
        corner="top right"
      />
    )}
  </IconGroup>
);

MultipleAffiliationsButton.propTypes = {
  person: PropTypes.object.isRequired,
  onEdit: PropTypes.func.isRequired,
  disabled: PropTypes.bool.isRequired,
};

export const customFields = ['jacowAffiliationsIds'];
