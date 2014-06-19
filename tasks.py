""" Specific Fabric tasks """

from datetime import datetime
import time
import os

from fabric.api import cd, env, local, lcd, run, get, put
from fabric.decorators import task
from fabric.contrib.files import exists

from .helpers import (
        test_connection, get_master_slave, select_servers,
        get_settings_file,
        wget, fmt_date,
        replace_tag, check_for_existing_tag,
        )



################
# Basic tasks
################

@task
def prepare_release(tag=None):
    """ Git tag all modules in env.modules, pin tags in prd-sources.cfg and tag buildout """

    if not tag:
        tag = '{}-{}'.format(env.appenv, fmt_date())

    def git_tag(tag):
        # XXX why commit? and why tag -f?
        local('git commit -am "tagging production release"')
        local('git tag -af {} -m "tagged production release"'.format(tag))
        local('git push --tags -f')
        local('git push')

    modules = env.modules

    existing_tag = False
    if check_for_existing_tag(tag):
        print('Buildout already tagged with tag {0}'.format(tag))
        existing_tag = True
    for m in modules:
        srcdir = os.path.join('src', m)
        if check_for_existing_tag(tag, repo=srcdir):
            print('Git module {0} already tagged with tag {1}'.format(m, tag))
            existing_tag = True
    if existing_tag:
        return  # don't reuse tag

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
                lines = line.split()

                if tag in line:
                    print('Git module {0} already pinned, skipping.')
                    continue

                if lines[0] in modules:
                    line = replace_tag(tag, lines)

                fout.write(line)

    local('cp {0} {0}.old'.format(old_settings))
    local('mv {0} {1}'.format(new_settings, old_settings))

    if not check_for_existing_tag(tag):
        git_tag(tag)
        print('Tagged buildout with tag {0}'.format(tag))


################
# Layered tasks
################

@task
def check_cluster(layer='acc'):
    """ Check HA/DRBD cluster health """
    cluster = get_master_slave(env.deploy_info[layer]['hosts'], quiet=False)
    print('\n'.join(
        ['', 'Current cluster info for {0}:'.format(layer)] +
        ["\t{0} is {1}".format(k,v) for k,v in sorted(cluster.items())] +
        ['']))


@task
@select_servers
def test():
    """ Test connection """
    test_connection()


@task
@select_servers
def update(tag=None):
    """ Git pull modules in env.modules and restart instances """
    # git checkout/pull
    for m in env.modules:
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
            if tag:
                run('git checkout {0}'.format(tag))
            else:
                run('git pull')
    # restart
    instances = env.deploy_info[env.appenv]['ports']['instances']
    for instance, port in instances.items():
        run('current/bin/supervisorctl restart {0}'.format(instance))
        print('Sleeping 5 seconds before continuing')
        time.sleep(5)
        url = env.site_url.format(port)
        wget(url)


@task
@select_servers
def deploy(tag=None, buildout_dir=None):
    """ Create new buildout in release dir """
    if not buildout_dir:
        buildout_dir = os.path.join('releases', fmt_date())

    if not exists('~/bin/python'):
        run('virtualenv $HOME')
        run('~/bin/pip install -U setuptools')

    if not exists(buildout_dir):
        run('git clone {0} {1}'.format(env.buildout_uri, buildout_dir))
    with cd(buildout_dir):
        run('git fetch')
        if tag:
            run('git checkout {}'.format(tag))
        else:
            run('git pull', warn_only=True)
        config = 'buildout-{}.cfg'.format(env.appenv)
        put(local_path=get_settings_file(), remote_path=config)
        if not exists('bin/buildout'):
            run('~/bin/python bootstrap.py -c {}'.format(config))
        run('./bin/buildout -c {}'.format(config))


@task
@select_servers
def switch(buildout_dir=None):
    """ Switch supervisor in current buildout dir to latest buildout """
    if not buildout_dir:
        buildout_dir = os.path.join('releases', fmt_date())
    old_current = run("readlink current", warn_only=True)
    if old_current == buildout_dir:
        return

    if old_current.failed:
        run('{}/bin/supervisord'.format(buildout_dir))
        if env.is_master:
            run('{}/bin/zeo start'.format(buildout_dir))

    else:
        if env.is_master:
            run('{}/bin/zeo stop'.format(old_current))
            run('{}/bin/zeo start'.format(buildout_dir))
        run('{}/bin/supervisord'.format(buildout_dir), warn_only=True)
        time.sleep(15)

        services = 'crashmail haproxy varnish'
        run('{}/bin/supervisorctl stop {}'.format(old_current, services))
        run('{}/bin/supervisorctl start {}'.format(buildout_dir, services))

        instances = env.deploy_info[env.appenv]['ports']['instances']
        for instance, port in instances.items():
            run('{}/bin/supervisorctl stop {}'.format(old_current, instance))
            run('{}/bin/supervisorctl start {}'.format(buildout_dir, instance))
            print('Sleeping 5 seconds before continuing')
            time.sleep(5)
            url = env.site_url.format(port)
            wget(url)

        run('{}/bin/supervisorctl shutdown'.format(old_current))
        run('rm current')

    run('ln -s {} current'.format(buildout_dir))


@task
@select_servers
def copy():
    """ Copy database from server """
    zeo_base = env.deploy_info[env.appenv]['zeo-base']
    local('rm -rf var/filestorage var/blobstorage')
    get(remote_path=os.path.join(zeo_base, 'filestorage', 'Data.fs'),
            local_path='var/filestorage/Data.fs')
    get(remote_path=os.path.join(zeo_base, 'blobstorage'),
            local_path='var/blobstorage')

