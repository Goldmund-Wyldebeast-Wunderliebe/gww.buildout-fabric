""" Specific Fabric tasks """

import time
import os
from StringIO import StringIO

from fabric.api import cd, env, local, run, get, put, open_shell
from fabric.decorators import task
from fabric.contrib.files import exists
from .helpers import config_template, read_remote_config_files, select_servers, wget


def do_deploy(branch=None, tag=None, buildout_dir=None):
    appenv_info = env.deploy_info[env.appenv].copy()
    if not buildout_dir:
        buildout_dir = appenv_info['buildout'] or 'buildout'

    if not exists('~/bin/python'):
        run('virtualenv $HOME')
        run('~/bin/pip install -U setuptools')

    if not exists(buildout_dir):
        run('git clone {0} {1}'.format(env.buildout_uri, buildout_dir))
    with cd(buildout_dir):
        run('git status')
        run('git fetch', warn_only=True)
        if branch:
            run('git checkout {}'.format(branch))
        if tag:
            run('git checkout {}'.format(tag))
            appenv_info['tag'] = tag
        else:
            run('git pull', warn_only=True)
        read_remote_config_files(appenv_info)
        config = 'buildout-{}.cfg'.format(env.appenv)
        config_text = config_template('buildout-layer.cfg', appenv_info)
        put(local_path=StringIO(config_text), remote_path=config)
        run("git submodule init && git submodule update")
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

    if current_link:
        run('rm -f {}'.format(current_link))
        run('ln -s {} {}'.format(buildout_dir, current_link))

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
        for service in [s.split()[0] for s in services.split('\n') if s]:
            run('{}/bin/supervisorctl stop {}'.format(
                old_buildout, service))
            run('{}/bin/supervisorctl start {}'.format(
                buildout_dir, service))
            try:
                port = appenv_info['instances']['ports'][service]
                print('Sleeping 5 seconds before continuing')
                time.sleep(5)
                wget('http://localhost:{}/{}/'.format(
                    port, appenv_info['site_id']))
            except KeyError:
                pass
        if old_buildout != buildout_dir:
            # Stop old supervisor.  It should be empty now.
            run('{}/bin/supervisorctl shutdown'.format(old_buildout))
        run('{}/bin/supervisorctl status'.format(buildout_dir))

    if appenv_info.get('zeo',{}).get('base') and env.is_master:
        # zeo not running from supervisor
        run('{}/bin/zeo stop'.format(old_buildout), warn_only=True)
        run('{}/bin/zeo start'.format(buildout_dir))

    webserver = appenv_info.get('webserver')
    sitename = appenv_info.get('sitename')
    if webserver and sitename:
        config = 'sites-enabled/{}'.format(sitename)
        home_dir = run('echo $HOME')  # TODO: move to a more logical place?
        appenv_info['home_dir'] = home_dir
        config_text = config_template('{}.conf'.format(webserver), appenv_info)
        if exists(config):
            buf = StringIO()
            get(local_path=buf, remote_path=config)
            if buf.getvalue() == config_text:
                return  # whambamthankyoumam
        run('mkdir -p sites-enabled')
        put(local_path=StringIO(config_text), remote_path=config)
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

@task
@select_servers
def shell(buildout_dir=None):
    """ Execute some commands on server """
    appenv_info = env.deploy_info[env.appenv]
    if not buildout_dir:
        current_link = appenv_info.get('current_link')
        if current_link:
            buildout_dir = run("readlink {}".format(current_link), warn_only=True)
        if not buildout_dir:
            buildout_dir = appenv_info.get('buildout') or 'buildout'

    open_shell("cd {}".format(buildout_dir))

@task
@select_servers
def hatop(buildout_dir=None):
    appenv_info = env.deploy_info[env.appenv]
    if not env.is_master:
        print env.host_string, 'not master'
        return
    if 'haproxy' not in appenv_info:
        print 'haproxy not in', appenv_info.keys()
        return
    print 'yes'
    if not buildout_dir:
        current_link = appenv_info.get('current_link')
        if current_link:
            buildout_dir = run("readlink {}".format(current_link), warn_only=True)
        if not buildout_dir:
            buildout_dir = appenv_info.get('buildout') or 'buildout'
    open_shell('cd {} && exec /usr/bin/python ./hatop -s var/run/haproxy-socket'.format(buildout_dir))

