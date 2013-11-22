from datetime import datetime
import time
from fabric.api import cd, env, local, lcd, run, sudo, settings
from fabric.contrib.files import exists

# env.user = 'app-ha-acc'
# env.hosts = ('46.22.180.90', )

env.subsite_urls = dict(
    nuffic='http://localhost:{0}/nuffic-site/nuffic/',
    ha='http://localhost:{0}/nuffic-han/www.hollandalumni.nl/'
)

env.buildouts = dict(
    nuffic='git@git.gw20e.com:buildout-nuffic.git',
    ha='git@git.gw20e.com:buildout-nuffic-han.git'
)


nuffic_modules = ('nuffic.theme', 'Products.NufficATContent')
han_modules = ('nuffic.theme', 'Products.NufficATContent', 'nuffic.han.content')

def get_environment():
    env = run('env | grep ENVIRONMENT')
    print env
    if env:
        return env.replace('ENVIRONMENT=', '')

def get_application():
    app = run('env | grep APPLICATION')
    if app:
        return app.replace('APPLICATION=', '')

def get_instance_ports():
    env = get_environment()
    ports = run('cat current/{0}-settings.cfg |grep "instance[0-9]-port"'.format(env))
    return [int(x.split('=')[1].lstrip()) for x in ports.replace('\r', '').split('\n')]

def modules():
    app = get_application()
    if app == 'nuffic':
        return nuffic_modules
    elif app == 'ha':
        return han_modules


def update_here():
    for m in modules:
        with lcd('src/{0}'.format(m)):
            local('git pull')

def pull_modules():
    app_env = get_environment()

    for m in modules():    
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
            run('git pull')

def restart_instances():
    app_env = get_environment()
    app = get_application()

    instance_ports = get_instance_ports()        

    for i, port in enumerate(instance_ports):
        run('current/bin/supervisorctl restart instance{0}'.format(i))
        print 'Waiting for instance{0} http connection...'.format(i)
        time.sleep(30)
        url = env.subsite_urls.get(app)
        url = url.format(port)
        run('wget {0} -O /dev/null'.format(url))

def deploy_buildout():
    app = get_application()
    app_env = get_environment()

    now = datetime.now()
    buildout_dir = '{0}-{1}-{2}'.format(now.day, now.month, now.year)   

    with cd('releases'):

        if not exists(buildout_dir):
            run('git clone {0} {1}'.format(env.buildouts.get(app), buildout_dir))

        with cd(buildout_dir):
            if not exists('bin/buildout'):
                run('git checkout responsive')
                run('cp ~/current/{0}-settings.cfg .'.format(app_env))
                run('~/bin/python bootstrap.py -c buildout-{0}.cfg'.format(app_env))

            run('./bin/buildout -c buildout-{0}.cfg'.format(app_env))

            run('./bin/supervisord')
            run('~/current/bin/supervisorctl stop crashmail')
            run('./bin/supervisorctl stop crashmail')
            run('~/current/bin/supervisorctl stop haproxy;')
            run('./bin/supervisorctl start haproxy')

            instance_ports = get_instance_ports()  

            for i, port in enumerate(instance_ports):
                run('~/current/bin/supervisorctl stop instance{0}'.format(i))
                run('./bin/supervisorctl start instance{0}'.format(i))

                time.sleep(30)
                url = env.subsite_urls.get(app)
                url = url.format(port)
                run('wget {0} -O /dev/null'.format(url))

    run('~/current/bin/supervisorctl shutdown')
    run('rm ~/current')
    run('ln -s releases/{0} current'.format(buildout_dir))
    run('~/current/bin/supervisorctl start crashmail')

def update_modules():
    pull_modules()
    restart_instances()
