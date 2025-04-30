// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import countriesURL from 'indico-url:plugin_jacow.countries';
import createAffiliationURL from 'indico-url:plugin_jacow.create_affiliation';
import searchAffiliationURL from 'indico-url:users.api_affiliations';

import _ from 'lodash';
import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {DndProvider} from 'react-dnd';
import {HTML5Backend} from 'react-dnd-html5-backend';
import {
  Dropdown,
  Header,
  Icon,
  IconGroup,
  List,
  Popup,
  Ref,
  Segment,
  Message,
} from 'semantic-ui-react';

import {FinalInput, FinalDropdown, FinalField} from 'indico/react/forms';
import {FinalModalForm, handleSubmitError} from 'indico/react/forms/final-form';
import {useIndicoAxios} from 'indico/react/hooks';
import {Param} from 'indico/react/i18n';
import {SortableWrapper, useSortableItem} from 'indico/react/sortable';
import {indicoAxios, handleAxiosError} from 'indico/utils/axios';
import {camelizeKeys} from 'indico/utils/case';
import {makeAsyncDebounce} from 'indico/utils/debounce';

import {Translate} from './i18n';

import './MultipleAffiliationsSelector.module.scss';

const debounce = makeAsyncDebounce(250);

const affiliationSchema = PropTypes.shape({
  id: PropTypes.number.isRequired,
  text: PropTypes.string.isRequired,
  meta: PropTypes.object.isRequired,
});

const extraParamsSchema = PropTypes.shape({
  jacowAffiliations: PropTypes.bool,
});

const getSubheader = ({city, countryName}) => {
  if (city && countryName) {
    return `${city}, ${countryName}`;
  }
  return city || countryName;
};

const DraggableAffiliation = ({affiliation, onDelete, index, onMove}) => {
  const [dragRef, itemRef, style] = useSortableItem({
    type: 'affiliation',
    index,
    moveItem: onMove,
    separateHandle: true,
  });

  return (
    <div ref={itemRef} style={style} styleName="affiliation">
      <Ref innerRef={dragRef}>
        <div className="icon-drag-indicator" styleName="handle" />
      </Ref>
      <Header
        style={{fontSize: 14}}
        content={affiliation.meta.name}
        subheader={getSubheader(affiliation.meta)}
      />
      <Icon name="remove" color="red" size="large" styleName="delete" onClick={onDelete} link />
    </div>
  );
};

DraggableAffiliation.propTypes = {
  affiliation: affiliationSchema.isRequired,
  onDelete: PropTypes.func.isRequired,
  index: PropTypes.number.isRequired,
  onMove: PropTypes.func.isRequired,
};

const MultipleAffiliationsField = ({onChange, value, currentAffiliations}) => {
  const [searchUsed, setSearchUsed] = useState(false);
  const [_searchResults, setSearchResults] = useState([]);
  const searchResults = [
    ...currentAffiliations,
    ..._searchResults.filter(x => !currentAffiliations.find(y => y.id === x.id)),
  ].filter(x => !value.find(y => y.meta.id === x.id));

  const affiliationOptions = searchResults.map(res => ({
    key: res.id,
    value: res.id,
    text: res.name,
    meta: res,
    content: <Header style={{fontSize: 14}} content={res.name} subheader={getSubheader(res)} />,
  }));

  const searchChange = async (evt, {searchQuery}) => {
    if (!searchQuery) {
      setSearchResults([]);
      return;
    }
    let resp;
    try {
      resp = await debounce(() => indicoAxios.get(searchAffiliationURL({q: searchQuery})));
    } catch (error) {
      handleAxiosError(error);
      return;
    }
    setSearchResults(camelizeKeys(resp.data));
    setSearchUsed(true);
  };

  const addItem = (evt, {value: newId}) => {
    const newValue = searchResults.find(x => x.id === newId);
    onChange([...value, {id: newValue.id, text: newValue.name, meta: newValue}]);
    setSearchResults([]);
  };

  const moveItem = (dragIndex, hoverIndex) => {
    const result = value.slice();
    result.splice(hoverIndex, 0, ...result.splice(dragIndex, 1));
    onChange(result);
  };

  return (
    <>
      <DndProvider backend={HTML5Backend}>
        <Segment attached="top">
          <SortableWrapper accept="affiliation">
            <List divided relaxed>
              {value.length > 0 ? (
                value.map((affiliation, idx) => (
                  <DraggableAffiliation
                    key={affiliation.id}
                    index={idx}
                    onMove={moveItem}
                    affiliation={affiliation}
                    onDelete={() => onChange(value.filter((_, i) => i !== idx))}
                  />
                ))
              ) : (
                <Translate>There are no affiliations</Translate>
              )}
            </List>
          </SortableWrapper>
        </Segment>
        <Segment attached="bottom">
          <Dropdown
            icon="search"
            placeholder={Translate.string('Add affiliations...')}
            options={affiliationOptions}
            onSearchChange={searchChange}
            onChange={addItem}
            onBlur={() => setSearchResults([])}
            selectOnBlur={false}
            selectOnNavigation={false}
            search={options => options}
            selection
            fluid
          />
        </Segment>
      </DndProvider>
      {searchUsed && (
        <Message info>
          <Translate>
            If you cannot find your affiliation, it may not yet be part of the{' '}
            <Param name="ror" wrapper={<a href="https://ror.org/" />}>
              ROR registry
            </Param>{' '}
            from which Indico gets its list of affiliations. Please{' '}
            <Param
              name="add_affiliation"
              wrapper={
                <AddAffiliation
                  onAdded={aff => {
                    onChange([...value, {id: aff.id, text: aff.name, meta: aff}]);
                  }}
                />
              }
            >
              add it to Indico yourself
            </Param>
            .
          </Translate>
        </Message>
      )}
    </>
  );
};

MultipleAffiliationsField.propTypes = {
  onChange: PropTypes.func.isRequired,
  value: PropTypes.arrayOf(affiliationSchema).isRequired,
  currentAffiliations: PropTypes.array.isRequired,
};

export default function MultipleAffiliationsSelector({
  persons,
  selected,
  onChange,
  onClose,
  modalOpen,
  extraParams,
}) {
  const onSubmit = ({affiliationsData}) => {
    const value = persons[selected];
    value.jacowAffiliationsIds = affiliationsData.map(x => x.id);
    value.jacowAffiliationsMeta = affiliationsData.map(x => x.meta);
    value.affiliation = affiliationsData.map(x => x.text.trim()).join('; ');
    onChange(persons.map((v, idx) => (idx === selected ? value : v)));
    onClose();
  };

  if (!extraParams.jacowAffiliations || modalOpen !== 'jacow_affiliations') {
    return null;
  }

  return (
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
      <FinalField
        name="affiliationsData"
        component={MultipleAffiliationsField}
        currentAffiliations={persons[selected].jacowAffiliationsMeta || []}
      />
    </FinalModalForm>
  );
}

MultipleAffiliationsSelector.propTypes = {
  persons: PropTypes.array.isRequired,
  selected: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  modalOpen: PropTypes.string.isRequired,
  extraParams: extraParamsSchema.isRequired,
};

const isoToFlag = country =>
  String.fromCodePoint(...country.split('').map(c => c.charCodeAt() + 0x1f1a5));

function StringListField({value, disabled, onChange, onFocus, onBlur, placeholder}) {
  const [searchQuery, setSearchQuery] = useState('');
  const isValid = v => !!v.trim();
  const options = value.filter(isValid).map(x => ({text: x, value: x}));

  const setValue = newValue => {
    newValue = _.uniq(newValue.filter(isValid));
    onChange(newValue);
    onFocus();
    onBlur();
  };

  const handleChange = (e, {value: newValue}) => {
    if (newValue.length && newValue[newValue.length - 1] === searchQuery) {
      setSearchQuery('');
    }
    setValue(newValue);
  };

  const handleSearchChange = (e, {searchQuery: newSearchQuery}) => {
    setSearchQuery(newSearchQuery);
  };

  const handleBlur = () => {
    if (isValid(searchQuery)) {
      setValue([...value, searchQuery.trim()]);
      setSearchQuery('');
    }
  };

  return (
    <Dropdown
      options={options}
      value={value}
      searchQuery={searchQuery}
      disabled={disabled}
      searchInput={{onFocus, onBlur, type: 'text'}}
      search
      selection
      multiple
      allowAdditions
      fluid
      open={!!searchQuery}
      placeholder={placeholder}
      additionLabel={Translate.string('Add') + ' '} // eslint-disable-line prefer-template
      onChange={handleChange}
      onSearchChange={handleSearchChange}
      onBlur={handleBlur}
      selectedLabel={null}
      icon=""
    />
  );
}

StringListField.propTypes = {
  value: PropTypes.arrayOf(PropTypes.string).isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
  onFocus: PropTypes.func.isRequired,
  onBlur: PropTypes.func.isRequired,
};

function AddAffiliation({children, onAdded}) {
  const {data: countries} = useIndicoAxios(countriesURL());
  const [modalOpen, setModalOpen] = useState(false);

  const onSubmit = async data => {
    let resp;
    try {
      resp = await indicoAxios.post(createAffiliationURL(), data);
    } catch (e) {
      return handleSubmitError(e);
    }
    onAdded(resp.data);
    setModalOpen(false);
  };

  return (
    <>
      <a onClick={() => setModalOpen(true)}>
        <strong>{children}</strong>
      </a>
      {modalOpen && (
        <FinalModalForm
          id="add-affiliation"
          size="tiny"
          onClose={() => setModalOpen(false)}
          onSubmit={onSubmit}
          initialValues={{alt_names: []}}
          header={Translate.string('Create new affiliation')}
          submitLabel={Translate.string('Create')}
        >
          <Message visible warning>
            <Translate>
              Please fill in this form carefully to avoid typos. Double-check that the name of the
              institute/company is the official name, and add commonly used alternative names such
              as acroyms in the "alternative names" field (one per line), this will help people find
              the one you're adding instead of creating a duplicate one. DO NOT add affiliations
              using this form unless you searched for them first and could not find them!
            </Translate>
          </Message>
          <FinalInput
            name="name"
            label={Translate.string('Official name')}
            placeholder={Translate.string('e.g. European Organization for Nuclear Research')}
            type="text"
            required
          />
          <FinalField
            name="alt_names"
            label={Translate.string('Alternative names')}
            placeholder={Translate.string('e.g. CERN')}
            component={StringListField}
            isEqual={_.isEqual}
          />
          <FinalInput name="city" label={Translate.string('City')} type="text" required />
          <FinalDropdown
            name="country_code"
            label={Translate.string('Country')}
            required
            fluid
            selection
            placeholder={Translate.string('Select a country')}
            parse={x => x}
            options={(countries ?? []).map(([name, title]) => ({
              key: name,
              value: name,
              text: `${isoToFlag(name)} ${title}`,
            }))}
          />
        </FinalModalForm>
      )}
    </>
  );
}

AddAffiliation.propTypes = {
  children: PropTypes.node,
  onAdded: PropTypes.func.isRequired,
};

export function MultipleAffiliationsButton({person, onEdit, disabled, extraParams}) {
  if (!extraParams.jacowAffiliations) {
    return null;
  }
  return (
    <Popup
      content={Translate.string('Edit affiliations')}
      disabled={disabled || !person.email}
      trigger={
        <IconGroup size="large">
          <Icon
            name="building"
            color={person.jacowAffiliationsIds?.length ? 'blue' : 'grey'}
            onClick={() => onEdit('jacow_affiliations')}
            disabled={disabled || !person.email}
            link={!(disabled || !person.email)}
          />
          {!person.jacowAffiliationsIds?.length && (
            <Icon
              name="exclamation circle"
              title={Translate.string('No affiliations added')}
              color="red"
              corner="top right"
              disabled={disabled || !person.email}
            />
          )}
        </IconGroup>
      }
    />
  );
}

MultipleAffiliationsButton.propTypes = {
  person: PropTypes.object.isRequired,
  onEdit: PropTypes.func.isRequired,
  disabled: PropTypes.bool.isRequired,
  extraParams: extraParamsSchema.isRequired,
};

export const customFields = ['jacowAffiliationsIds'];

export const onAddPersonLink = person => {
  if (!person.jacowAffiliationsIds && person.affiliationId) {
    person.jacowAffiliationsIds = [person.affiliationId];
    person.jacowAffiliationsMeta = [person.affiliationMeta];
  }
};
