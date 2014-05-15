""" Specific Fabric tasks """

import logging
import time
import os
from fabric.api import task, cd, env, local, lcd, run, sudo, settings
from fabric.decorators import task, hosts
from fabric.contrib.files import exists

from helpers import (get_application, get_environment, get_instance_ports,
    wget, fmt_date, replace_tag, get_modules, check_for_existing_tag)

@task
def prepare_release():
    """ Git tag all modules in env.modules, pin tags in prd-sources.cfg and tag buildout """

    def git_tag(tag):
        local('git commit -am "tagging production release"')
        local('git tag -af {} -m "tagged production release"'.format(tag))
        local('git push --tags -f')
        local('git push')

    buildout_path = os.getcwd()
    modules = env.modules
    tag = 'prd-{}'.format(fmt_date())

    for m in modules:
        with lcd('{0}/src/{1}'.format(buildout_path, m)):

            if not check_for_existing_tag(tag):
                local('''sed -i.org 's/version = .*/version = "{}"/' setup.py'''.format(tag))
                git_tag(tag)
                print('Tagged git module {0} with tag {1}'.format(m, tag))
            else:
                print('Git module {0} already tagged with tag {1}'.format(m, tag))

    old_settings = '{}/prd-sources.cfg'.format(buildout_path)
    new_settings = '{}/prd-sources.cfg.new'.format(buildout_path)

    if os.path.isfile(old_settings):    
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

        with lcd(buildout_path):
            if not check_for_existing_tag(tag):
                git_tag(tag)
                print('Tagged buildout with tag {0}'.format(tag))
            else:
                print('Buildout already tagged with tag {0}'.format(tag))
    else:
        print(
            '\nCannot set tags in prd-settings.cfg, add your git module '
            '(ending with rev=dummy) to this config.'
        )
        raise

@task
def pull_modules(tag=None):
    """ Git pull module on remote buildout """
    for m in get_modules():
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
            if tag:
                run('git checkout {0}'.format(tag))
            run('git pull')

@task
def restart_instances():
    """ Restarts all instances in remote buildout """
    app = get_application()

    instance_ports = get_instance_ports()

    for i, port in enumerate(instance_ports):
        run('~/current/bin/supervisorctl restart instance{0}'.format(i))
        url = env.site_url.format(port)
        wget(url)

@task
def deploy_buildout(tag=None):
    """ Deploys a new buildout """
    app = get_application()
    app_env = get_environment()

    buildout_dir = fmt_date()

    if not tag:
        tag = 'prd-{}'.format(fmt_date())

    if not exists('releases'):
        run('mkdir releases')
    with cd('releases'):

        if not exists(buildout_dir):
            run('git clone {0} {1}'.format(env.buildout_uri, buildout_dir))

        with cd(buildout_dir):
            if not exists('bin/buildout'):

                if exists('~/current/{0}-settings.cfg .'.format(app_env)):
                    run('cp ~/current/{0}-settings.cfg .'.format(app_env))
                else:
                    try:
                        run('cp ~/current/{0}-settings.cfg .'.format(app_env))
                    except:
                        if not exists('~/releases/initial'):
                            run('mkdir -p ~/releases/initial', warn_only=True)
                            run('ln -s ~/releases/initial ~/current', warn_only=True)
                        print(
                            '\nYou need to provide ~/current/{0}-settings.cfg '
                            'file in home folder to create initial buildout.\n'
                            'Copy config using: \n'
                            '  cp ~/releases/{1}/example-{0}-settings.cfg ~/current/{0}-settings.cfg'
                            .format(app_env, buildout_dir)
                        )
                        if app_env == 'acc':
                            print(
                                '\nMake sure the database paths on acceptance are not in the buildout directory.\n'
                                'This way the same database can be reused when creating a new buildout release folder:\n'
                                '  [zeo]\n'
                                '  file-storage = /opt/APPS/{0}/acc/db/filestorage/Data.fs\n'
                                '  blob-storage = /opt/APPS/{0}/acc/db/blobstorage\n'.format(app)
                            )
                        raise

                if not exists('~/bin/python'):
                    run('virtualenv-2.7 $HOME')
                    run('~/bin/pip install -U setuptools')

                run('~/bin/python bootstrap.py -c buildout-{0}.cfg'.format(app_env))

            run('git fetch')
            run('git checkout {}'.format(tag))
            run('git pull', warn_only=True)

            run('./bin/buildout -c buildout-{0}.cfg'.format(app_env))

@task
def switch_buildout(tag=None):
    """ Switch supervisor from old to current buildout """
    initial = False
    app_env = get_environment()
    buildout_dir = fmt_date()

    if not tag:
        tag = 'prd-{}'.format(fmt_date())

    output = run('ls -l ~/current')
    if 'releases/initial/' in output.split()[-1]:
        initial = True

    with cd('releases/{0}'.format(buildout_dir)):

        if initial:
            run('./bin/zeo start')

        if exists('./var/supervisord.pid'):
            run('./bin/supervisorctl shutdown')
            time.sleep(10)

        run('./bin/supervisord')
        time.sleep(15)

        if app_env == 'prd':
            run('~/current/bin/supervisorctl stop crashmail')
            run('./bin/supervisorctl stop crashmail')

        if exists('~/current/bin/supervisorctl'):
            run('~/current/bin/supervisorctl stop haproxy varnish')
            run('./bin/supervisorctl start haproxy varnish')

        instance_ports = get_instance_ports()

        for i, port in enumerate(instance_ports):
            run('./bin/supervisorctl start instance{0}'.format(i))
            if exists('~/current/bin/supervisorctl'):
                run('~/current/bin/supervisorctl stop instance{0}'.format(i))

            print('Sleeping 30 seconds before continueing')
            time.sleep(30)

            if not initial:
                url = env.site_url.format(port)
                wget(url)

    if exists('~/current/bin/supervisorctl'):
        run('~/current/bin/supervisorctl shutdown')
    run('rm ~/current')
    run('ln -s releases/{0} current'.format(buildout_dir))

#@task
def get_master_slave(hosts, quiet=True):
    """ Returns hostnames for master and slave """

    if not hosts:
        raise ValueError(u'No hosts defined')
    elif len(hosts) == 1:
        return dict(master=hosts[0])
    elif len(hosts) != 2:
        raise ValueError(u'It seems this is not master/slave setup')

    cluster = dict(master=None, slave=None)    

    for host in hosts:
        with settings(host_string=host):
            output = run('cat /proc/drbd', quiet=quiet)
            if 'Primary/Secondary' in output: 
                cluster['master'] = host
            elif 'Secondary/Primary' in output: 
                cluster['slave'] = host
            else:
                raise ValueError(u'DRBD problem!')

    if not (cluster['master'] and cluster['slave']):
        raise ValueError(u'No master/slave server setup found!')

    return cluster

#@task
def test_connection():
    """ Task to test if the connection is working """

    print(u'Testing fabric connection for {0}'.format(env.host_string))
    run('hostname ; whoami ; pwd')
