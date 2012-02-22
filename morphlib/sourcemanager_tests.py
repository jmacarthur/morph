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


import glob
import unittest
import tempfile
import shutil
import os
import subprocess
import urlparse

import morphlib


class DummyApp(object):

    def __init__(self):
        self.settings = {
            'git-base-url': ['.',],
            'bundle-server': None,
            'cachedir': '/foo/bar/baz',
            'ignore-submodules': False
        }
        self.msg = lambda msg: None


class SourceManagerTests(unittest.TestCase):

    def setUp(self):
        self.temprepodir = tempfile.mkdtemp()
        env = os.environ
        env["DATADIR"]=self.temprepodir
        subprocess.call("./tests/show-dependencies.setup", shell=True, env=env)
        self.temprepo = self.temprepodir + '/test-repo/'
        bundle_name = morphlib.sourcemanager.quote_url(self.temprepo) + '.bndl'
        with open('/dev/null', 'w') as f:
            subprocess.check_call("git bundle create %s/%s master" %
                                    (self.temprepodir, bundle_name),
                                  stderr=f, shell=True, cwd=self.temprepo)

    def tearDown(self):
        shutil.rmtree(self.temprepodir)

    def test_uses_provided_cache_dir(self):
        return
        app = DummyApp()
        
        tempdir = '/bla/bla/bla'
        s = morphlib.sourcemanager.SourceManager(app, tempdir)
        self.assertEqual(s.cache_dir, tempdir)

    def test_uses_cachedir_gits_if_no_cache_dir_provided(self):
        app = DummyApp()

        s = morphlib.sourcemanager.SourceManager(app)
        self.assertEqual(s.cache_dir,
                         os.path.join(app.settings['cachedir'], 'gits'))

    def test_resolves_sha1_treeish_for_test_repo_correctly(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)

    def test_resolves_sha1_treeish_for_test_repo_correctly_twice(self):
        tempdir = tempfile.mkdtemp()

        # try two times with different source manager objects
        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        # try two times with the same source manager object
        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)

    def test_resolves_ref_treeish_for_test_repo_correctly(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo, 'master')
        self.assertEquals(t.ref, 'refs/remotes/origin/master')

        shutil.rmtree(tempdir)

    def test_resolves_ref_treeish_for_test_repo_without_submodules(self):
        tempdir = tempfile.mkdtemp()

        s = morphlib.sourcemanager.SourceManager(DummyApp(), tempdir)
        t = s.get_treeish(self.temprepo, 'master')
        self.assertEquals(len(t.submodules), 0)

        shutil.rmtree(tempdir)

    def test_resolves_sha1_treeish_for_test_repo_correctly_from_bundle(self):
        tempdir = tempfile.mkdtemp()
        bundle_server_loc = self.temprepodir

        app = DummyApp()
        app.settings['bundle-server'] = 'file://' + bundle_server_loc

        s = morphlib.sourcemanager.SourceManager(app, tempdir)

        def wget(url, filename):
            bundle_file = os.path.join(self.temprepodir,
                                       os.path.basename(filename))
            shutil.copy(bundle_file, s.cache_dir)

        s._wget = wget

        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)

    def test_fails_to_resolves_sha1_treeish_for_non_existent_repo(self):
        tempdir = tempfile.mkdtemp()
        app = DummyApp()

        s = morphlib.sourcemanager.SourceManager(app, tempdir)

        def wget(url, filename):
            bundle_file = os.path.join(self.temprepodir,
                                       os.path.basename(filename))
            shutil.copy(bundle_file, s.cache_dir)

        s._wget = wget
        self.assertRaises(morphlib.sourcemanager.RepositoryFetchError,
                          s.get_treeish, 'asdf',
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)

    def test_fails_to_resolves_sha1_treeish_for_non_existent_repo_bundle(self):
        tempdir = tempfile.mkdtemp()
        app = DummyApp()
        app.settings['bundle-server'] = 'file://' + self.temprepodir

        s = morphlib.sourcemanager.SourceManager(app, tempdir)

        def wget(url, filename):
            bundle_file = os.path.join(self.temprepodir,
                                       os.path.basename(filename))
            shutil.copy(bundle_file, s.cache_dir)

        s._wget = wget
        self.assertRaises(morphlib.sourcemanager.RepositoryFetchError,
                          s.get_treeish, 'asdf',
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)

    def test_get_sha1_treeish_for_self_multiple_base(self):

        tempdir = tempfile.mkdtemp()
        app = DummyApp()
        app.settings['git-base-url'] = ['.', '/somewhere/else']

        s = morphlib.sourcemanager.SourceManager(app, tempdir)
        t = s.get_treeish(self.temprepo,
                          'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')
        self.assertEquals(t.sha1, 'e28a23812eadf2fce6583b8819b9c5dbd36b9fb9')

        shutil.rmtree(tempdir)
