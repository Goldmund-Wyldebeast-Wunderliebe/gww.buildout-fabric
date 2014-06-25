""" Specific Fabric tasks """

import os
from datetime import datetime
import itertools

from fabric.api import env, local, lcd
from fabric.decorators import task


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


def git_command(repo, command):
    return local('( cd {} && git {} )'.format(repo, command), capture=True)

def current_tags(repo):
    return git_command(repo, 'tag').split()

def git_add_tag(repo, tag, comment=None):
    git_command(repo, 'tag {} -m "{}"'.format(tag, comment or ''))
    git_command(repo, 'push --tags')

def git_hash(repo, tag=''):
    return git_command(repo, 'log -n1 --pretty=format:%h {}'.format(tag))

def try_and_tag_all(tag, repositories, comment=None):
    """ returns list of conflicting modules if not succesful """
    repos_with_this_tag = []
    repos_with_conflict = []
    for repo in repositories:
        if tag in current_tags(repo):
            repos_with_this_tag.append(repo)
            if git_hash(repo) != git_hash(repo, tag):
                repos_with_conflict.append(repo)
    if repos_with_conflict:
        return repos_with_conflict
    for repo in repositories:
        if repo in repos_with_this_tag:
            continue
        git_add_tag(repo, tag, comment=comment)
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

    if tag:
        conflicts = try_and_tag_all(tag, repositories, comment=comment)
        if conflicts:
            print("Conflict for tag {} in module {}".format(
                tag, ", ".join(conflicts)))
            ERROR
        return tag
    else:
        for tag in invent_tag():
            conflicts = try_and_tag_all(tag, repositories, comment=comment)
            if not conflicts:
                return tag


@task
@select_servers
def make_eggs():

    # read versions.cfg


    for m in modules:
        srcdir = os.path.join('src', m)
        if not check_for_existing_tag(tag, repo=srcdir):
            with lcd(srcdir):
                #local('''sed -i.org 's/version = .*/version = "{}"/' setup.py'''.format(tag))
                # XXX Modify version in setup.py if we intend jarn.mkrelease,
                # and tag is like "1.1.5".  That only makes sense on a single
                # module, not in this case.
                # If tag is something like "sprint7", we dont' modify the
                # module, just add a tag.
                git_tag(tag)
                print('Tagged git module {0} with tag {1}'.format(m, tag))

    old_settings = 'prd-sources.cfg'
    new_settings = 'prd-sources.cfg.new'

    if not os.path.isfile(old_settings):
        print(
            '\nCannot set tags in prd-settings.cfg, add your git module '
            '(ending with rev=dummy) to this config.'
        )
        raise

    local('touch {}'.format(new_settings))

    print('\nChanging tags in prd-settings.cfg, make sure your module is in prd-settings.cfg.')
    with open(new_settings, 'wt') as fout:
        with open(old_settings, 'rt') as fin:
            for line in fin:
                line = replace_tag(line, tag, modules)
                fout.write(line)

    local('cp {0} {0}.old'.format(old_settings))
    local('mv {0} {1}'.format(new_settings, old_settings))

    if not check_for_existing_tag(tag):
        git_tag(tag)
        print('Tagged buildout with tag {0}'.format(tag))

