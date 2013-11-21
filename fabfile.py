import time
from fabric.api import cd, env, local, lcd, run, sudo, settings


env.user = 'app-ha-acc'
env.hosts = ('46.22.180.90', )
env.subsite_urls = dict(
    nuffic=None,
    ha='http://localhost:{0}/nuffic-han/www.hollandalumni.nl/'
)

nuffic_modules = ('nuffic.theme', 'Products.NufficATContent')
han_modules = ('nuffic.theme', 'Products.NufficATContent', 'nuffic.han.content')

def get_environment():
    env = run('env | grep ENVIRONMENT')
    if env:
        return env.replace('ENVIRONMENT=', '')

def get_application():
    app = run('env | grep APPLICATION')
    if app:
        return app.replace('APPLICATION=', '')

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

def update():
    app_env = get_environment()

    for m in modules():    
        print 'Updating {0}'.format(m)
        with cd('current/src/{0}'.format(m)):
            run('git pull')

def restart_instances():
    def get_ports(env):
        ports = run('cat current/{0}-settings.cfg |grep "instance[0-9]-port"'.format(env))
        return [int(x.split('=')[1].lstrip()) for x in ports.replace('\r', '').split('\n')]

    app_env = get_environment()
    app = get_application()

    instance_ports = get_ports(app_env)        

    for i, port in enumerate(instance_ports):
        run('current/bin/supervisorctl restart instance{0}'.format(i))
        print 'Waiting for instance{0} http connection...'.format(i)
        time.sleep(30)
        url = env.subsite_urls.get(app)
        url = url.format(port)
        run('wget {0} -O /dev/null'.format(url))

def deploy():
    update()
    restart_instances()

    




    


