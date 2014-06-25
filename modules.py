""" Specific Fabric tasks """

import os
import re
from datetime import datetime
import itertools

from fabric.api import env, local, lcd
from fabric.decorators import task

from .helpers import select_servers


"""
Two workflows for getting modules to the remote (tst/acc/prd) buildout.

    A:  Use mr.developer to git checkout. Individual modules and the buildout
        will be tagged, and the tag will be in the [sources] section of the
        generated buildout-xxx.cfg.  If the tag already exists and is different
        from the (local) checked-out version, we refuse.

    B:  Use eggs. For each module in versions.cfg that's checked out here, we
        verify that the version is up-to-date: a corresponding tag should exist
        and be the checked-out version.
        Use jarn.mkrelease to make/distribute/tag.

"""


class MLGR(object):
    """ my little git repo class... will be refactored later """
    tag_pattern = re.compile('([^(), \s]+)')

    def __init__(self, repo):
        self.repo = repo
        self.is_repo = os.path.isdir(os.path.join(repo, '.git'))
        if not self.is_repo:
            return
        self.all_tags = self.git_command('tag').split()
        self.top_tags = [name
                for name in self.tag_pattern.findall(self.git_command(
                    'log', '-n1', '--pretty=format:%d'))
                if name in self.all_tags]

    def __nonzero__(self):
        return self.is_repo

    def add_tag(repo, tag, comment=None):
        self.git_command('tag', tag, '-m', comment or '')
        self.git_command('push', '--tags')

    def git_command(self, *command):
        return local(
                '( cd "{}" && git {} )'.format(
                    self.repo, " ".join('"%s"'%a for a in command)),
                capture=True)

    def __repr__(self):
        return self.repo


def try_and_tag_all(tag, repositories, comment=None):
    """ returns list of conflicting modules if not succesful """
    repos_with_this_tag = []
    repos_with_conflict = []
    for repo in repositories:
        if tag in repo.top_tags:
            repos_with_conflict.append(repo)
        elif tag in repo.all_tags:
            repos_with_this_tag.append(repo)
    if repos_with_conflict:
        return repos_with_conflict
    for repo in repositories:
        repo.add_tag(tag, comment=comment)
    return None

def invent_tag():
    appenv_info = env.deploy_info[env.appenv]
    tag_format = appenv_info.get('tag_format', env.appenv + '-%Y%m%d')
    now = datetime.now()
    for x in itertools.count():
        suffix = '-%d' % x if x else ''
        yield now.strftime(tag_format) + suffix


@task
@select_servers
def make_tags(tag=None, comment=None):
    """ Git tag all modules and buildout """
    appenv_info = env.deploy_info[env.appenv]
    modules = appenv_info.get('modules')
    repositories = ['.'] + ['src/'+m for m in modules]
    repositories = [MLGR(repo) for repo in repositories]

    if tag:
        conflicts = try_and_tag_all(tag, repositories, comment=comment)
        if conflicts:
            print("Conflict for tag {} in module {}".format(
                tag, ", ".join(conflicts)))
            ERROR
        break
    else:
        for tag in invent_tag():
            conflicts = try_and_tag_all(tag, repositories, comment=comment)
            if not conflicts:
                break
    print 'tag {} is everywhere now'.format(tag)


@task
def check_versions():
    from ConfigParser import SafeConfigParser
    versions = SafeConfigParser()
    versions.read('versions.cfg')
    if not versions.has_section('versions'):
        print "versions.cfg doesn't have a [versions] section"
        return
    # *** NoSectionError: No section: 'versions'
    # ('setuptools', '> 0.9.8'), ('raven', '4.0.4-gww.1'), ...
    for module, version in versions.items('versions'):
        repo = MLGR(os.path.join('src', module))
        if not repo:
            print 'no module {}'.format(module)
        elif version not in repo.all_tags:
            print 'tag {} not found in {}'.format(version, module)
        elif version not in repo.top_tags:
            print 'tag {} is not latest commit in {}'.format(version, module)
        else:
            print 'tag {} is latest in {} -- OK!'.format(version, module)


@task
@select_servers
def make_eggs():
    pass  # NYI

