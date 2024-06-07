// This file is part of the JACoW plugin.
// Copyright (C) 2021 - 2024 CERN
//
// The CERN Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License; see
// the LICENSE file for more details.

import PropTypes from 'prop-types';
import React, {useState} from 'react';
import {Button, Dropdown} from 'semantic-ui-react';

import {Translate} from 'indico/react/i18n';

import {FinalSingleFileManager} from 'indico/react/components';

const PeerReviewManagersFileInput = ({}) => {

}

export default function PeerReviewManagersFileField ({}) {

}

export function PeerReviewManagersFileButton ({fieldId}) {
    console.log(fieldId);
    if (fieldId !== 'judges' && fieldId !== 'content_reviewers'){
        return null
    }
    return (
        <>
            <Button icon='download' as='div'/>
            <Button icon='upload' as='div'/>
        </>
    )
}
