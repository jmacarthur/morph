# Copyright (C) 2012  Codethink Limited
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


import unittest

import morphlib


class LocalArtifactCacheTests(unittest.TestCase):

    def setUp(self):
        self.tempdir = morphlib.tempdir.Tempdir()

        morph = morphlib.morph2.Morphology(
                '''
                {
                    "chunk": "chunk",
                    "kind": "chunk",
                    "artifacts": {
                        "chunk-runtime": [
                            "usr/bin",
                            "usr/sbin",
                            "usr/lib",
                            "usr/libexec"
                        ],
                        "chunk-devel": [
                            "usr/include"
                        ]
                    }
                }
                ''')
        self.source = morphlib.source.Source(
                'repo', 'ref', 'sha1', morph, 'chunk.morph')
        self.runtime_artifact = morphlib.artifact.Artifact(
                self.source, 'chunk-runtime', 'cachekey')
        self.devel_artifact = morphlib.artifact.Artifact(
                self.source, 'chunk-devel', 'cachekey')

    def tearDown(self):
        self.tempdir.remove()

    def test_put_artifacts_and_check_whether_the_cache_has_them(self):
        cache = morphlib.localartifactcache.LocalArtifactCache(
                self.tempdir.dirname)

        handle = cache.put(self.runtime_artifact)
        handle.write('runtime')
        handle.close()

        self.assertTrue(cache.has(self.runtime_artifact))

        handle = cache.put(self.devel_artifact)
        handle.write('devel')
        handle.close()

        self.assertTrue(cache.has(self.runtime_artifact))
        self.assertTrue(cache.has(self.devel_artifact))

    def test_put_artifacts_and_get_them_afterwards(self):
        cache = morphlib.localartifactcache.LocalArtifactCache(
                self.tempdir.dirname)

        handle = cache.put(self.runtime_artifact)
        handle.write('runtime')
        handle.close()

        handle = cache.get(self.runtime_artifact)
        stored_data = handle.read()
        handle.close()

        self.assertEqual(stored_data, 'runtime')

        handle = cache.put(self.devel_artifact)
        handle.write('devel')
        handle.close()

        handle = cache.get(self.runtime_artifact)
        stored_data = handle.read()
        handle.close()

        self.assertEqual(stored_data, 'runtime')

        handle = cache.get(self.devel_artifact)
        stored_data = handle.read()
        handle.close()

        self.assertEqual(stored_data, 'devel')

    def test_put_check_and_get_artifact_metadata(self):
        cache = morphlib.localartifactcache.LocalArtifactCache(
                self.tempdir.dirname)

        handle = cache.put_artifact_metadata(self.runtime_artifact, 'log')
        handle.write('log line 1\nlog line 2\n')
        handle.close()

        self.assertTrue(cache.has_artifact_metadata(
            self.runtime_artifact, 'log'))

        handle = cache.get_artifact_metadata(self.runtime_artifact, 'log')
        stored_metadata = handle.read()
        handle.close()

        self.assertEqual(stored_metadata, 'log line 1\nlog line 2\n')

    def test_put_check_and_get_source_metadata(self):
        cache = morphlib.localartifactcache.LocalArtifactCache(
                self.tempdir.dirname)

        handle = cache.put_source_metadata(self.source, 'mycachekey', 'log')
        handle.write('source log line 1\nsource log line 2\n')
        handle.close()

        self.assertTrue(cache.has_source_metadata(
            self.source, 'mycachekey', 'log'))

        handle = cache.get_source_metadata(self.source, 'mycachekey', 'log')
        stored_metadata = handle.read()
        handle.close()

        self.assertEqual(stored_metadata,
                         'source log line 1\nsource log line 2\n')