// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2025 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import {registerPluginComponent, registerPluginObject} from 'indico/utils/plugins';

import MultipleAffiliationsSelector, {
  MultipleAffiliationsButton,
  customFields,
  onAddPersonLink,
} from './MultipleAffiliationsSelector';
import {PeerReviewManagersFileButton} from './PeerReviewManagersFileInput';

const PLUGIN_NAME = 'jacow';

registerPluginComponent(PLUGIN_NAME, 'personListItemActions', MultipleAffiliationsButton);
registerPluginComponent(PLUGIN_NAME, 'personLinkFieldModals', MultipleAffiliationsSelector);
registerPluginComponent(
  PLUGIN_NAME,
  'principal-list-field-add-buttons',
  PeerReviewManagersFileButton
);
registerPluginObject(PLUGIN_NAME, 'personLinkCustomFields', customFields);
registerPluginObject(PLUGIN_NAME, 'onAddPersonLink', onAddPersonLink);
