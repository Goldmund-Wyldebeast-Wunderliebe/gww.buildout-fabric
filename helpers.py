from fabric.api import cd, env, local, lcd, run, sudo, settings

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