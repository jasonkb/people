#!/usr/bin/env python

import glob
import json
import os
import sys
import yaml
import yamlordereddictloader
from collections import defaultdict, OrderedDict
from utils import reformat_phone_number

# set up defaultdict representation
from yaml.representer import Representer
yaml.add_representer(defaultdict, Representer.represent_dict)


def all_people(dirname):
    memberships = defaultdict(list)
    organizations = {}

    for filename in glob.glob(os.path.join(dirname, 'organization_*.json')):
        with open(filename) as f:
            organization = json.load(f)
            organizations[organization['_id']] = organization

    for filename in glob.glob(os.path.join(dirname, 'membership_*.json')):
        with open(filename) as f:
            membership = json.load(f)
            membership['organization'] = organizations.get(membership['organization_id'])
            memberships[membership['person_id']].append(membership)

    for filename in glob.glob(os.path.join(dirname, 'person_*.json')):
        with open(filename) as f:
            person = json.load(f)
            person['memberships'] = memberships[person['_id']]
            yield person


def filename_for_person(person):
    return '{name}-{_id}.yml'.format(**person)


def postprocess_link(link):
    if not link['note']:
        del link['note']
    return link


def postprocess_person(person):
    optional_keys = (
        'image',
        'gender',
        'biography',
        'birth_date',
        'death_date',
        'national_identity',
        'summary',
        'extras',
        # maybe post-process these?
        'identifiers',
        'other_names',
    )

    result = OrderedDict(
        id=person['_id'],
        name=person['name'],
        party=[],
        roles=[],
        links=[postprocess_link(link) for link in person['links']],
        contact_details=[],
        # maybe post-process these?
        sources=[postprocess_link(link) for link in person['sources']],
        committees=[],
    )

    contact_details = defaultdict(lambda: defaultdict(list))
    for detail in person['contact_details']:
        value = detail['value']
        if detail['type'] in ('voice', 'fax'):
            value = reformat_phone_number(value)
        contact_details[detail['note']][detail['type']] = value

    result['contact_details'] = [{'note': key, **val} for key, val in contact_details.items()]

    # memberships!
    for membership in person['memberships']:
        organization_id = membership['organization_id']
        if organization_id.startswith('~'):
            org = json.loads(organization_id[1:])
            if org['classification'] in ('upper', 'lower'):
                post = json.loads(membership['post_id'][1:])['label']
                result['roles'] = [
                    {'chamber': org['classification'], 'district': post}
                ]
            elif org['classification'] == 'party':
                result['party'] = [
                    {'name': org['name']}
                ]
        elif membership['organization']:
            result['committees'].append({
                'name': membership['organization']['name'],
            })
        else:
            raise ValueError(organization_id)

    for key in optional_keys:
        if person.get(key):
            result[key] = person[key]

    return result


def process_people(input_dir, output_dir):
    for person in all_people(input_dir):

        filename = filename_for_person(person)
        person = postprocess_person(person)

        with open(os.path.join(output_dir, filename), 'w') as f:
            yaml.dump(person, f, default_flow_style=False, Dumper=yamlordereddictloader.Dumper)


if __name__ == '__main__':
    input_dir = sys.argv[1]

    # state is last piece of directory name
    state = None
    for piece in input_dir.split('/')[::-1]:
        if piece:
            state = piece
            break

    output_dir = os.path.join(os.path.dirname(__file__), '../test/', state)

    try:
        os.makedirs(output_dir)
    except FileExistsError:
        for file in glob.glob(os.path.join(output_dir, '*.yml')):
            os.remove(file)
    process_people(input_dir, output_dir)