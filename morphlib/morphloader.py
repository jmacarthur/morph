# Copyright (C) 2013  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# =*= License: GPL-2 =*=


import logging
import yaml

import morphlib


class MorphologySyntaxError(morphlib.Error):

    def __init__(self, morphology):
        self.msg = 'Syntax error in morphology %s' % morphology


class NotADictionaryError(morphlib.Error):

    def __init__(self, morphology):
        self.msg = 'Not a dictionary: morphology %s' % morphology


class UnknownKindError(morphlib.Error):

    def __init__(self, kind, morphology):
        self.msg = (
            'Unknown kind %s in morphology %s' % (kind, morphology))


class MissingFieldError(morphlib.Error):

    def __init__(self, field, morphology):
        self.msg = (
            'Missing field %s from morphology %s' % (field, morphology))


class InvalidFieldError(morphlib.Error):

    def __init__(self, field, morphology):
        self.msg = (
            'Field %s not allowed in morphology %s' % (field, morphology))

class ObsoleteFieldError(morphlib.Error):

    def __init__(self, field, morphology):
       self.msg = (
            'Field %s is now obsolete but present in %s' % (field, morphology))

class UnknownArchitectureError(morphlib.Error):

    def __init__(self, arch, morphology):
        self.msg = (
            'Unknown architecture %s in morphology %s' % (arch, morphology))


class NoBuildDependenciesError(morphlib.Error):

    def __init__(self, stratum_name, chunk_name, morphology):
        self.msg = (
            'Stratum %s has no build dependencies for chunk %s in %s' %
                (stratum_name, chunk_name, morphology))


class NoStratumBuildDependenciesError(morphlib.Error):

    def __init__(self, stratum_name, morphology):
        self.msg = (
            'Stratum %s has no build dependencies in %s' %
                (stratum_name, morphology))


class EmptyStratumError(morphlib.Error):

    def __init__(self, stratum_name, morphology):
        self.msg = (
            'Stratum %s has no chunks in %s' %
                (stratum_name, morphology))


class MorphologyLoader(object):

    '''Load morphologies from disk, or save them back to disk.'''

    _required_fields = {
        'chunk': [
            'name',
        ],
        'stratum': [
            'name',
        ],
        'system': [
            'name',
            'arch',
        ],
        'cluster': [
          'name',
          'systems',
        ],
    }

    _obsolete_fields = {
        'system': [
            'system-kind',
            'disk-size',
        ],
    }

    _static_defaults = {
        'chunk': {
            'description': '',
            'pre-configure-commands': [],
            'configure-commands': [],
            'post-configure-commands': [],
            'pre-build-commands': [],
            'build-commands': [],
            'post-build-commands': [],
            'pre-test-commands': [],
            'test-commands': [],
            'post-test-commands': [],
            'pre-install-commands': [],
            'install-commands': [],
            'post-install-commands': [],
            'devices': [],
            'chunks': [],
            'max-jobs': None,
            'build-system': 'manual',
        },
        'stratum': {
            'chunks': [],
            'description': '',
            'build-depends': [],
        },
        'system': {
            'strata': [],
            'description': '',
            'arch': None,
            'configuration-extensions': [],
        },
        'cluster': {},
    }

    def parse_morphology_text(self, text, whence):
        '''Parse a textual morphology.

        The text may be a string, or an open file handle.

        Return the new Morphology object, or raise an error indicating
        the problem. This method does minimal validation: a syntactically
        correct morphology is fine, even if none of the fields are
        valid. It also does not set any default values for any of the
        fields. See validate and set_defaults.

        whence is where the morphology text came from. It is used
        in exception error messages.

        '''

        try:
            obj = yaml.safe_load(text)
        except yaml.error.YAMLError as e:
            logging.error('Could not load morphology as YAML:\n%s' % str(e))
            raise MorphologySyntaxError(whence)

        if not isinstance(obj, dict):
            raise NotADictionaryError(whence)

        return morphlib.morph3.Morphology(obj)

    def load_from_string(self, string, filename='string'):
        '''Load a morphology from a string.

        Return the Morphology object.

        '''

        m = self.parse_morphology_text(string, filename)
        m.filename = filename
        self.validate(m)
        self.set_defaults(m)
        return m

    def load_from_file(self, filename):
        '''Load a morphology from a named file.

        Return the Morphology object.

        '''

        with open(filename) as f:
            text = f.read()
        return self.load_from_string(text, filename=filename)

    def save_to_string(self, morphology):
        '''Return normalised textual form of morphology.'''

        return yaml.safe_dump(morphology.data, default_flow_style=False)

    def save_to_file(self, filename, morphology):
        '''Save a morphology object to a named file.'''

        text = self.save_to_string(morphology)
        with morphlib.savefile.SaveFile(filename, 'w') as f:
            f.write(text)

    def validate(self, morph):
        '''Validate a morphology.'''

        # Validate that the kind field is there.
        self._require_field('kind', morph)

        # The rest of the validation is dependent on the kind.

        # FIXME: move validation of clusters from morph2 to
        # here, and use morphload to load the morphology
        kind = morph['kind']
        if kind not in ('system', 'stratum', 'chunk', 'cluster'):
            raise UnknownKindError(morph['kind'], morph.filename)

        required = ['kind'] + self._required_fields[kind]
        obsolete = self._obsolete_fields.get(kind, [])
        allowed = self._static_defaults[kind].keys()
        self._require_fields(required, morph)
        self._deny_obsolete_fields(obsolete, morph)
        self._deny_unknown_fields(required + allowed, morph)

        if kind == 'system':
            self._validate_system(morph)
        elif kind == 'stratum':
            self._validate_stratum(morph)
        elif kind == 'chunk':
            self._validate_chunk(morph)
        else:
            assert kind == 'cluster'

    def _validate_system(self, morph):
        # All stratum names should be unique within a system.
        names = set()
        for spec in morph['strata']:
            name = spec.get('alias', spec['morph'])
            if name in names:
               raise ValueError('Duplicate stratum "%s"' % name)
            names.add(name)

        # We allow the ARMv7 little-endian architecture to be specified
        # as armv7 and armv7l. Normalise.
        if morph['arch'] == 'armv7':
            morph['arch'] = 'armv7l'

        # Architecture name must be known.
        if morph['arch'] not in morphlib.valid_archs:
            raise UnknownArchitectureError(morph['arch'], morph.filename)

    def _validate_stratum(self, morph):
        # Require at least one chunk.
        if len(morph.get('chunks', [])) == 0:
            raise EmptyStratumError(morph['name'], morph.filename)

        # All chunk names must be unique within a stratum.
        names = set()
        for spec in morph['chunks']:
            name = spec.get('alias', spec['name'])
            if name in names:
               raise ValueError('Duplicate chunk "%s"' % name)
            names.add(name)

        # Require build-dependencies for the stratum itself, unless
        # it has chunks built in bootstrap mode.
        if 'build-depends' not in morph:
            for spec in morph['chunks']:
                if spec.get('build-mode') in ['bootstrap', 'test']:
                    break
            else:
                raise NoStratumBuildDependenciesError(
                    morph['name'], morph.filename)

        # Require build-dependencies for each chunk.
        for spec in morph['chunks']:
            if 'build-depends' not in spec:
                raise NoBuildDependenciesError(
                    morph['name'],
                    spec.get('alias', spec['name']),
                    morph.filename)

    def _validate_chunk(self, morph):
        pass

    def _require_field(self, field, morphology):
        if field not in morphology:
            raise MissingFieldError(field, morphology.filename)

    def _require_fields(self, fields, morphology):
        for field in fields:
            self._require_field(field, morphology)

    def _deny_obsolete_fields(self, fields, morphology):
        for field in morphology:
            if field in fields:
                raise ObsoleteFieldError(field, morphology.filename)

    def _deny_unknown_fields(self, allowed, morphology):
        for field in morphology:
            if field not in allowed:
                raise InvalidFieldError(field, morphology.filename)

    def set_defaults(self, morphology):
        '''Set all missing fields in the morpholoy to their defaults.

        The morphology is assumed to be valid.

        '''

        kind = morphology['kind']
        defaults = self._static_defaults[kind]
        for key in defaults:
            if key not in morphology:
                morphology[key] = defaults[key]

        if kind == 'system':
            self._set_system_defaults(morphology)
        elif kind == 'stratum':
            self._set_stratum_defaults(morphology)
        elif kind == 'chunk':
            self._set_chunk_defaults(morphology)

    def unset_defaults(self, morphology):
        '''If a field is equal to its default, delete it.

        The morphology is assumed to be valid.

        '''

        kind = morphology['kind']
        defaults = self._static_defaults[kind]
        for key in defaults:
            if key in morphology and morphology[key] == defaults[key]:
                del morphology[key]

        if kind == 'stratum':
            self._unset_stratum_defaults(morphology)

    def _set_system_defaults(self, morph):
        pass

    def _set_stratum_defaults(self, morph):
        for spec in morph['chunks']:
            if 'repo' not in spec:
                spec['repo'] = spec['name']
            if 'morph' not in spec:
                spec['morph'] = spec['name']

    def _unset_stratum_defaults(self, morph):
        for spec in morph['chunks']:
            if 'repo' in spec and spec['repo'] == spec['name']:
                del spec['repo']
            if 'morph' in spec and spec['morph'] == spec['name']:
                del spec['morph']

    def _set_chunk_defaults(self, morph):
        if morph['max-jobs'] is not None:
            morph['max-jobs'] = int(morph['max-jobs'])

