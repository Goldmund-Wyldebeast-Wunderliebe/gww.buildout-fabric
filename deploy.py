""" Specific Fabric tasks """

import time
import os

from fabric.api import cd, env, local, run, get, put
from fabric.decorators import task
from fabric.contrib.files import exists
from .helpers import select_servers, config_template, wget


def do_update(tag=None, buildout_dir=None):
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info['buildout'] or 'buildout'

    modules = appenv_info.get('modules')
    instances = appenv_info.get('instances')
    if not (modules and instances):
        return

    # git checkout/pull
    for module, source in modules.items():
        print 'Updating {}'.format(module)
        with cd('{}/src/{}'.format(buildout_dir, module)):
            run('git pull', warn_only=True)
            if tag:
                run('git checkout {}'.format(tag))
    # restart
    for instance, port in instances['ports'].items():
        run('{}/bin/supervisorctl restart {}'.format(buildout_dir, instance))
        print('Sleeping 5 seconds before continuing')
        time.sleep(5)
        wget('http://localhost:{}/{}/'.format(port, appenv_info['site_id']))


def do_deploy(tag=None, buildout_dir=None):
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
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info.get('buildout') or 'buildout'

    current_link = appenv_info.get('current_link')
    if current_link:
        old_buildout = run("readlink current", warn_only=True)

    if current_link and old_buildout:
        # this is the hard case. stop stuff on old buildout, start it here.
        # NB: old_buildout might be same as buildout_dir, if redeploying or
        # updating today's buildout.
        # Gracefully migrate instances from old to new
        services = run('{}/bin/supervisorctl status'.format(old_buildout))
        if old_buildout != buildout_dir:
            run('{}/bin/supervisord'.format(buildout_dir), warn_only=True)
            print('Sleeping 15 seconds before continuing')
            time.sleep(15)
        for service in [s.split()[0] for s in services.split('\n')]:
            run('{}/bin/supervisorctl stop {}'.format(
                old_buildout, service))
            run('{}/bin/supervisorctl start {}'.format(
                buildout_dir, service))
            port = appenv_info['instances']['ports'].get(service)
            if port:
                print('Sleeping 5 seconds before continuing')
                time.sleep(5)
                wget('http://localhost:{}/{}/'.format(
                    port, appenv_info['site_id']))
        if old_buildout != buildout_dir:
            run('{}/bin/supervisorctl shutdown'.format(old_buildout))
        run('{}/bin/supervisorctl status'.format(buildout_dir))

        if appenv_info.get('zeo',{}).get('base') and env.is_master:
            # zeo not running from supervisor
            run('{}/bin/zeo stop'.format(old_buildout))
            run('{}/bin/zeo start'.format(buildout_dir))

    else:
        # not current_link, so not timestamped. just (re)start everything.
        # or first deploy on timestamped series. just start everything.
        run('{0}/bin/supervisorctl reload || {0}/bin/supervisord'.format(
            buildout_dir))
        # zeo not running from supervisor
        if appenv_info.get('zeo',{}).get('base') and env.is_master:
            run('{}/bin/zeo restart'.format(buildout_dir))

    if current_link:
        run('rm -f {}'.format(current_link))
        run('ln -s {} {}'.format(buildout_dir, current_link))

    webserver = appenv_info.get('webserver')
    sitename = appenv_info.get('sitename')
    if webserver and sitename:
        put(local_path=config_template('{}.conf'.format(webserver)),
                remote_path='~/sites-enabled/{}'.format(sitename))
        run('sudo /etc/init.d/{} reload'.format(webserver))


def do_copy(buildout_dir=None):
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


@task
@select_servers
def update(*args, **kwargs):
    """ Git pull modules in env.modules and restart instances """
    do_update(*args, **kwargs)

@task
@select_servers
def deploy(*args, **kwargs):
    """ Create new buildout in release dir """
    do_deploy(*args, **kwargs)

@task
@select_servers
def switch(*args, **kwargs):
    """ Switch supervisor in current buildout dir to latest buildout """
    do_switch(*args, **kwargs)

@task
@select_servers
def copy(*args, **kwargs):
    """ Copy database from server """
    do_copy(*args, **kwargs)

