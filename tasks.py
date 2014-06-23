""" Specific Fabric tasks """

from datetime import datetime
import time
import os

from fabric.api import cd, env, local, lcd, run, get, put
from fabric.decorators import task
from fabric.contrib.files import exists

from .helpers import (
        test_connection, get_master_slave, select_servers,
        config_template,
        wget,
        replace_tag, check_for_existing_tag,
        )



################
# Basic tasks
################

@task
def prepare_release(tag=None):
    """ Git tag all modules in env.modules, pin tags in prd-sources.cfg and tag buildout """

    if not tag:
        now = datetime.now()
        tag = '{}-{}'.format(env.appenv, now.strftime('%Y-%m-%d'))

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

def do_update(tag=None, buildout_dir=None):
    """ Git pull modules in env.modules and restart instances """
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info['buildout'] or 'buildout'

    # git checkout/pull
    for m in env.modules:
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
            if tag:
                run('git checkout {0}'.format(tag))
            else:
                run('git pull')
    # restart
    instances = appenv_info['ports']['instances']
    for instance, port in instances.items():
        run('current/bin/supervisorctl restart {0}'.format(instance))
        print('Sleeping 5 seconds before continuing')
        time.sleep(5)
        url = env.site_url.format(port)
        wget(url)


def do_deploy(tag=None, buildout_dir=None):
    """ Create new buildout in release dir """
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info['buildout'] or 'buildout'

    if not exists('~/bin/python'):
        run('virtualenv $HOME')
        run('~/bin/pip install -U setuptools')

    if not exists(buildout_dir):
        run('git clone {0} {1}'.format(env.buildout_uri, buildout_dir))
    with cd(buildout_dir):
        run('git pull', warn_only=True)
        if tag:
            run('git checkout {}'.format(tag))
        config = 'buildout-{}.cfg'.format(env.appenv)
        put(local_path=config_template('buildout-layer.cfg'),
                remote_path=config)
        if not exists('bin/buildout'):
            run('~/bin/python bootstrap.py -c {}'.format(config))
        run('./bin/buildout -c {}'.format(config))

    if appenv_info.get('auto_switch', True):
        do_switch(buildout_dir=buildout_dir)


def do_switch(buildout_dir=None):
    """ Switch supervisor in current buildout dir to latest buildout """
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info.get('buildout') or 'buildout'

    current_link = appenv_info.get('current_link')
    if current_link:
        old_buildout = run("readlink current", warn_only=True)
    if current_link and old_buildout and old_buildout != buildout_dir:
        # this is the hard case. stop stuff on old buildout, start it here.
        run('{}/bin/supervisorctl shutdown'.format(old_buildout))
        run('rm {}'.format(current_link))
        run('{}/bin/supervisord'.format(buildout_dir))
        if zeo and zeo.base and env.is_master:
            # zeo not running from supervisor
            run('{}/bin/zeo stop'.format(old_buildout))
            run('{}/bin/zeo start'.format(buildout_dir))

        # XXX this stops all old instances before starting the new ones.
        # A more graceful approach is wanted.
        if False:
            run('{}/bin/supervisord'.format(buildout_dir), warn_only=True)
            time.sleep(15)
            services = 'crashmail haproxy varnish'
            run('{}/bin/supervisorctl stop {}'.format(old_buildout, services))
            run('{}/bin/supervisorctl start {}'.format(buildout_dir, services))
            instances = appenv_info['ports']['instances']
            for instance, port in instances.items():
                run('{}/bin/supervisorctl stop {}'.format(
                    old_buildout, instance))
                run('{}/bin/supervisorctl start {}'.format(
                    buildout_dir, instance))
                print('Sleeping 5 seconds before continuing')
                time.sleep(5)
                url = env.site_url.format(port)
                wget(url)

    else:
        # not current_link, so not timestamped. just (re)start everything.
        # or first deploy on timestamped series. just start everything.
        # or redeploy to today's buildout. just restart everything.
        run('{0}/bin/supervisorctl reload || {0}/bin/supervisord'.format(
            buildout_dir))
        # zeo not running from supervisor
        if appenv_info.get('zeo',{}).get('base') and env.is_master:
            #if not zeorunning:
                run('{}/bin/zeo start'.format(buildout_dir))

    if current_link:
        run('ln -s ~/{} {}'.format(buildout_dir, current_link))

    webserver = appenv_info.get('webserver')
    sitename = appenv_info.get('sitename')
    if webserver and sitename:
        put(local_path=config_template('{}.conf'.format(webserver)),
                remote_path='~/sites-enabled/{}'.format(sitename))
        run('sudo /etc/init.d/{} reload'.format(webserver))


def do_copy(buildout_dir=None):
    """ Copy database from server """
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info.get('buildout') or 'buildout'

    if not env.is_master:
        return
    if 'zeo' in appenv_info:
        zeo_base = appenv_info['zeo']['base']  # fails if zeo is separate
    else:
        zeo_base = os.path.join(buildout_dir, 'var')
    local('rm -rf var/filestorage var/blobstorage')
    get(remote_path=os.path.join(zeo_base, 'filestorage', 'Data.fs'),
            local_path='var/filestorage/Data.fs')
    get(remote_path=os.path.join(zeo_base, 'blobstorage'),
            local_path='var/blobstorage')


################

@task
def check_cluster(layer='default'):
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
def update(*args, **kwargs):
    do_update(*args, **kwargs)

@task
@select_servers
def deploy(*args, **kwargs):
    do_deploy(*args, **kwargs)

@task
@select_servers
def switch(*args, **kwargs):
    do_switch(*args, **kwargs)

@task
@select_servers
def copy(*args, **kwargs):
    do_copy(*args, **kwargs)

