""" Specific Fabric tasks """

import time
import os

from fabric.api import cd, env, local, run, get, put
from fabric.decorators import task
from fabric.contrib.files import exists
from .helpers import select_servers, config_template, wget


def do_deploy(branch=None, tag=None, buildout_dir=None):
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        buildout_dir = appenv_info['buildout'] or 'buildout'

    if not exists('~/bin/python'):
        run('virtualenv $HOME')
        run('~/bin/pip install -U setuptools')

    if not exists(buildout_dir):
        run('git clone {0} {1}'.format(env.buildout_uri, buildout_dir))
    with cd(buildout_dir):
        run('git fetch', warn_only=True)
        if branch:
            run('git checkout {}'.format(branch))
        if tag:
            run('git checkout {}'.format(tag))
        else:
            run('git pull', warn_only=True)
        config = 'buildout-{}.cfg'.format(env.appenv)
        put(local_path=config_template('buildout-layer.cfg', tag=tag),
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

    # See if there's an old buildout that this one is replacing.
    # If not, old_buildout is same as buildout_dir
    current_link = appenv_info.get('current_link')
    old_buildout = None
    if current_link:
        old_buildout = run("readlink {}".format(current_link), warn_only=True)
    if not old_buildout:
        old_buildout= buildout_dir

    # If there's no supervisor running in old_buildout, things are easy.
    if run('{}/bin/supervisorctl update'.format(old_buildout), warn_only=True).failed:
        # Easy. Just start supervisor and be the hero of the day.
        run('{}/bin/supervisord'.format(buildout_dir), warn_only=True)
    else:
        # OK, not easy.  Stop stuff on old buildout, start it here.
        # If old_buildout == buildout_dir, we're redeploying or updating
        # today's buildout.
        services = run('{}/bin/supervisorctl status'.format(old_buildout))
        if old_buildout != buildout_dir:
            # Start new supervisor.
            run('{}/bin/supervisord'.format(buildout_dir), warn_only=True)
            time.sleep(1)
        # Gracefully migrate services from old to new.
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
            # Stop old supervisor.  It should be empty now.
            run('{}/bin/supervisorctl shutdown'.format(old_buildout))
        run('{}/bin/supervisorctl status'.format(buildout_dir))

    if appenv_info.get('zeo',{}).get('base') and env.is_master:
        # zeo not running from supervisor
        run('{}/bin/zeo stop'.format(old_buildout), warn_only=True)
        run('{}/bin/zeo start'.format(buildout_dir))

    if current_link:
        run('rm -f {}'.format(current_link))
        run('ln -s {} {}'.format(buildout_dir, current_link))

    webserver = appenv_info.get('webserver')
    sitename = appenv_info.get('sitename')
    if webserver and sitename:
        config = '~/sites-enabled/{}'.format(sitename)
        config_tmp = os.path.join(buildout_dir, 'tmp-'+sitename)
        put(local_path=config_template('{}.conf'.format(webserver)),
                remote_path=config_tmp)
        run("""
            if cmp -s {config} {config_tmp}
            then rm {config_tmp}
            else mv {config_tmp} {config}
                 sudo /etc/init.d/{webserver} reload
            fi
        """.format(config=config, config_tmp=config_tmp, webserver=webserver))


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
            local_path='var/blobstorage')   # XXX rsync


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

