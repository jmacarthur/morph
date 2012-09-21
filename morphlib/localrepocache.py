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


import logging
import os
import re
import urllib2
import urlparse
import shutil
import string

import cliapp

import morphlib


# urlparse.urljoin needs to know details of the URL scheme being used.
# It does not know about git:// by default, so we teach it here.
gitscheme = ['git']
urlparse.uses_relative.extend(gitscheme)
urlparse.uses_netloc.extend(gitscheme)
urlparse.uses_params.extend(gitscheme)
urlparse.uses_query.extend(gitscheme)
urlparse.uses_fragment.extend(gitscheme)


def quote_url(url):
    ''' Convert URIs to strings that only contain digits, letters, % and _.

    NOTE: When changing the code of this function, make sure to also apply
    the same to the quote_url() function of lorry. Otherwise the git bundles
    generated by lorry may no longer be found by morph.

    '''
    valid_chars = string.digits + string.letters + '%_'
    transl = lambda x: x if x in valid_chars else '_'
    return ''.join([transl(x) for x in url])


class NoRemote(morphlib.Error):

    def __init__(self, reponame, errors):
        self.reponame = reponame
        self.errors = errors

    def __str__(self):
        return '\n\t'.join(['Cannot find remote git repository: %s' %
                            self.reponame] + self.errors)


class NotCached(morphlib.Error):
    def __init__(self, reponame):
        self.reponame = reponame

    def __str__(self):  # pragma: no cover
        return 'Repository %s is not cached yet' % self.reponame


class LocalRepoCache(object):

    '''Manage locally cached git repositories.

    When we build stuff, we need a local copy of the git repository.
    To avoid having to clone the repositories for every build, we
    maintain a local cache of the repositories: we first clone the
    remote repository to the cache, and then make a local clone from
    the cache to the build environment. This class manages the local
    cached repositories.

    Repositories may be specified either using a full URL, in a form
    understood by git(1), or as a repository name to which a base url
    is prepended. The base urls are given to the class when it is
    created.

    Instead of cloning via a normal 'git clone' directly from the
    git server, we first try to download a bundle from a url, and
    if that works, we clone from the bundle.

    '''

    def __init__(self, app, cachedir, resolver, bundle_base_url=None):
        self._app = app
        self._cachedir = cachedir
        self._resolver = resolver
        if bundle_base_url and not bundle_base_url.endswith('/'):
            bundle_base_url += '/'  # pragma: no cover
        self._bundle_base_url = bundle_base_url
        self._cached_repo_objects = {}

    def _exists(self, filename):  # pragma: no cover
        '''Does a file exist?

        This is a wrapper around os.path.exists, so that unit tests may
        override it.

        '''

        return os.path.exists(filename)

    def _git(self, args, cwd=None):  # pragma: no cover
        '''Execute git command.

        This is a method of its own so that unit tests can easily override
        all use of the external git command.

        '''

        self._app.runcmd(['git'] + args, cwd=cwd)

    def _fetch(self, url, filename):  # pragma: no cover
        '''Fetch contents of url into a file.

        This method is meant to be overridden by unit tests.

        '''
        self._app.status(msg="Trying to fetch %(bundle)s to seed the cache",
                         bundle=url,
                         chatty=True)
        source_handle = None
        try:
            source_handle = urllib2.urlopen(url)
            with open(filename, 'wb') as target_handle:
                shutil.copyfileobj(source_handle, target_handle)
            self._app.status(msg="Bundle fetch successful",
                             chatty=True)
        except Exception, e:
            self._app.status(msg="Bundle fetch failed: %(reason)s",
                             reason=e,
                             chatty=True)
            raise
        finally:
            if source_handle is not None:
                source_handle.close()

    def _mkdir(self, dirname):  # pragma: no cover
        '''Create a directory.

        This method is meant to be overridden by unit tests.

        '''

        os.mkdir(dirname)

    def _remove(self, filename):  # pragma: no cover
        '''Remove given file.

        This method is meant to be overridden by unit tests.

        '''

        os.remove(filename)

    def _rmtree(self, dirname):  # pragma: no cover
        '''Remove given directory tree.

        This method is meant to be overridden by unit tests.

        '''

        shutil.rmtree(dirname)

    def _escape(self, url):
        '''Escape a URL so it can be used as a basename in a file.'''

        # FIXME: The following is a nicer way than to do this.
        # However, for compatibility, we need to use the same as the
        # bundle server (set up by Lorry) uses.
        # return urllib.quote(url, safe='')

        return quote_url(url)

    def _cache_name(self, url):
        basename = self._escape(url)
        path = os.path.join(self._cachedir, basename)
        return path

    def has_repo(self, reponame):
        '''Have we already got a cache of a given repo?'''
        url = self._resolver.pull_url(reponame)
        path = self._cache_name(url)
        return self._exists(path)

    def _clone_with_bundle(self, repourl, path):
        escaped = self._escape(repourl)
        bundle_url = urlparse.urljoin(self._bundle_base_url, escaped) + '.bndl'
        bundle_path = path + '.bundle'

        try:
            self._fetch(bundle_url, bundle_path)
        except urllib2.URLError, e:
            return False, 'Unable to fetch bundle %s: %s' % (bundle_url, e)

        try:
            self._git(['clone', '--mirror', '-n', bundle_path, path])
            self._git(['remote', 'set-url', 'origin', repourl], cwd=path)
        except cliapp.AppException, e:  # pragma: no cover
            if self._exists(path):
                shutil.rmtree(path)
            return False, 'Unable to extract bundle %s: %s' % (bundle_path, e)
        finally:
            if self._exists(bundle_path):
                self._remove(bundle_path)

        return True, None

    def cache_repo(self, reponame):
        '''Clone the given repo into the cache.

        If the repo is already cloned, do nothing.

        '''
        errors = []
        if not self._exists(self._cachedir):
            self._mkdir(self._cachedir)

        try:
            return self.get_repo(reponame)
        except NotCached, e:
            pass

        if self._bundle_base_url:
            repourl = self._resolver.pull_url(reponame)
            path = self._cache_name(repourl)
            ok, error = self._clone_with_bundle(repourl, path)
            if ok:
                return self.get_repo(reponame)
            else:
                errors.append(error)

        repourl = self._resolver.pull_url(reponame)
        path = self._cache_name(repourl)
        try:
            self._git(['clone', '--mirror', '-n', repourl, path])
        except cliapp.AppException, e:
            errors.append('Unable to clone from %s to %s: %s' %
                          (repourl, path, e))
            raise NoRemote(reponame, errors)

        return self.get_repo(reponame)

    def get_repo(self, reponame):
        '''Return an object representing a cached repository.'''

        if reponame in self._cached_repo_objects:
            return self._cached_repo_objects[reponame]
        else:
            repourl = self._resolver.pull_url(reponame)
            path = self._cache_name(repourl)
            if self._exists(path):
                repo = morphlib.cachedrepo.CachedRepo(self._app, reponame,
                                                      repourl, path)
                self._cached_repo_objects[reponame] = repo
                return repo
        raise NotCached(reponame)
