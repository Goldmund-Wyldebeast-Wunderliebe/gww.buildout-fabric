""" Specific Fabric tasks """

import time
from fabric.api import task, cd, env, local, lcd, run, sudo, settings
from fabric.decorators import task, hosts
from fabric.contrib.files import exists

from helpers import (get_application, get_environment, get_instance_ports,
    wget, fmt_date, replace_tag, get_modules)

@task
def prepare_release():
    """ Tag all modules in get_modules located in buildout path """

    def git_tag(tag):
        local('git commit -am "tagging production release"')
        # TODO: check if tag if exists, if so silently fail/continue
        # http://stackoverflow.com/questions/3418674/bash-shell-script-function-to-verify-git-tag-or-commit-exists-and-has-been-pushe
        local('git tag -af {} -m "tagged production release"'.format(tag))
        local('git push --tags -f')
        local('git push')

    # TODO: find out CWD for buildout_path
    buildout_path = ''
    modules = get_modules(app_env)
    tag = 'prd-{}'.format(fmt_date())

   

    for m in modules:
        print 'Tagging module: {0}'.format(m)
        # TODO: check if tag if exists, if so silently fail/continue
        with lcd('{0}/src/{1}'.format(buildout_path, m)):
            local('''sed -i.org 's/version = .*/version = "{}"/' setup.py'''.format(tag))
            git_tag(tag)

    old_settings = '{}/prd-sources.cfg'.format(buildout_path)
    new_settings = '{}/prd-sources.cfg.new'.format(buildout_path)
    local('touch {}'.format(new_settings))

    print 'Changing tags in prd-settings.cfg'
    with open(new_settings, 'wt') as fout:
        with open(old_settings, 'rt') as fin:
            for line in fin:

                lines = line.split()

                if lines[0] in modules:
                    line = replace_tag(tag, lines)

                fout.write(line)

    local('cp {0} {0}.old'.format(old_settings))
    local('mv {0} {1}'.format(new_settings, old_settings))

    with lcd(buildout_path):
        git_tag(tag)

@task
def pull_modules():
    """ Git pull module on remote buildout """
    for m in get_modules():
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
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
        time.sleep(120)


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
                        print 'You need to provide %s file in home folder to create initial buildout'%'~/current/{0}-settings.cfg .'.format(app_env)
                        raise

                # TODO: check for python/virtualenv
                run('~/bin/python bootstrap.py -c buildout-{0}.cfg'.format(app_env))

            run('git fetch')
            run('git checkout {}'.format(tag))
            run('git pull', warn_only=True)

            run('./bin/buildout -c buildout-{0}.cfg'.format(app_env))

@task
def switch_buildout(tag=None):
    """ Switch supervisor from old to current buildout """
    app_env = get_environment()

    buildout_dir = fmt_date()

    if not tag:
        tag = 'prd-{}'.format(fmt_date())

    with cd('releases/{0}'.format(buildout_dir)):
        
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
                    run('~/current/bin/supervisorctl stop instance{0}'.format(i))
                    run('./bin/supervisorctl start instance{0}'.format(i))
                    time.sleep(30)

                    url = env.site_url.format(port)
                    wget(url)

    if exists('~/current/bin/supervisorctl'):
        run('~/current/bin/supervisorctl shutdown')
    run('rm ~/current')
    run('ln -s releases/{0} current'.format(buildout_dir))

@task
def get_master_slave(quiet=True):
    """ Returns hostnames for master and slave """

    if type(env.prd_hosts) != tuple:
        raise ValueError(u'It seems this setup does not have multiple prd servers')

    cluster = dict(master=None, slave=None)    

    for login in env.prd_hosts:
        with settings(host_string=login):
            output = run(
                'cat /proc/drbd | grep \'Primary/Secondary\'', 
                warn_only=True, 
                quiet=quiet
            )
            if output:
                cluster['master'] = login
            else:
                cluster['slave'] = login

    if not (cluster['master'] or cluster['slave']):
        raise ValueError(u'No master and/or slave server found!')

    return cluster

@task
def test_connection():
    """ Task to test if the connection is working """

    print u'Testing fabric connection for {0} on {1}'.format(env.user, env.host)
    run('uname -a')
    run('whoami')
    run('ls -l')
