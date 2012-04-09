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


import os
import shutil
import tempfile
import unittest

import morphlib


def touch(pathname):
    with open(pathname, 'w'):
        pass


def create_manual_project(srcdir):
    pass


def create_autotools_project(srcdir):
    touch(os.path.join(srcdir, 'configure.in'))
    
    
class BuildSystemTests(unittest.TestCase):

    def setUp(self):
        self.bs = morphlib.buildsystem.BuildSystem()

    def test_has_configure_commands(self):
        self.assertEqual(self.bs['configure-commands'], [])

    def test_has_build_commands(self):
        self.assertEqual(self.bs['build-commands'], [])

    def test_has_test_commands(self):
        self.assertEqual(self.bs['test-commands'], [])

    def test_has_install_commands(self):
        self.assertEqual(self.bs['install-commands'], [])
        
    def test_returns_morphology_text(self):
        self.bs.name = 'fake'
        text = self.bs.get_morphology_text('foobar')
        self.assertTrue(type(text) in (str, unicode))


class ManualBuildSystemTests(unittest.TestCase):

    def setUp(self):
        self.bs = morphlib.buildsystem.ManualBuildSystem()
        self.tempdir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)
        
    def exists(self, filename):
        return os.path.exists(os.path.join(self.tempdir, filename))
        
    def test_does_not_autodetect_empty(self):
        create_manual_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))
        
    def test_does_not_autodetect_autotools(self):
        create_autotools_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))


class DummyBuildSystemTests(unittest.TestCase):

    def setUp(self):
        self.bs = morphlib.buildsystem.DummyBuildSystem()
        self.tempdir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)
        
    def exists(self, filename):
        return os.path.exists(os.path.join(self.tempdir, filename))
        
    def test_does_not_autodetect_empty(self):
        create_manual_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))
        
    def test_does_not_autodetect_autotools(self):
        create_autotools_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))


class AutotoolsBuildSystemTests(unittest.TestCase):

    def setUp(self):
        self.bs = morphlib.buildsystem.ManualBuildSystem()
        self.tempdir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)
        
    def exists(self, filename):
        return os.path.exists(os.path.join(self.tempdir, filename))
        
    def test_does_not_autodetect_empty(self):
        create_manual_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))
        
    def test_autodetects_autotools(self):
        create_autotools_project(self.tempdir)
        self.assertFalse(self.bs.used_by_project(self.exists))


class DetectBuildSystemTests(unittest.TestCase):

    def setUp(self):
        self.bs = morphlib.buildsystem.ManualBuildSystem()
        self.tempdir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.tempdir)
        
    def exists(self, filename):
        return os.path.exists(os.path.join(self.tempdir, filename))

    def test_does_not_autodetect_manual(self):
        create_manual_project(self.tempdir)
        bs = morphlib.buildsystem.detect_build_system(self.exists)
        self.assertEqual(bs, None)

    def test_autodetects_autotools(self):
        create_autotools_project(self.tempdir)
        bs = morphlib.buildsystem.detect_build_system(self.exists)
        self.assertEqual(type(bs), morphlib.buildsystem.AutotoolsBuildSystem)


class LookupBuildSystemTests(unittest.TestCase):

    def lookup(self, name):
        return morphlib.buildsystem.lookup_build_system(name)

    def test_raises_keyerror_for_unknown_name(self):
        self.assertRaises(KeyError, self.lookup, 'unkonwn')

    def test_looks_up_manual(self):
        self.assertEqual(type(self.lookup('manual')),
                         morphlib.buildsystem.ManualBuildSystem)

    def test_looks_up_autotools(self):
        self.assertEqual(type(self.lookup('autotools')),
                         morphlib.buildsystem.AutotoolsBuildSystem)

    def test_looks_up_dummy(self):
        self.assertEqual(type(self.lookup('dummy')),
                         morphlib.buildsystem.DummyBuildSystem)
