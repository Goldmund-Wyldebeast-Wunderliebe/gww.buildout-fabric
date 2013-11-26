import time
from datetime import datetime
from fabric.api import cd, env, local, lcd, run, sudo, settings

try:
    from config import nuffic_modules, han_modules, local_buildouts
except ImportError:
    nuffic_modules = ('nuffic.theme', 'Products.NufficATContent')
    han_modules = ('nuffic.theme', 'Products.NufficATContent', 'nuffic.han.content')
    local_buildouts = None


def get_modules(app=None):
    """ Returns Python get_modules for appie env """
    if not app:
        app = get_application()

    if app == 'nuffic':
        return nuffic_modules
    elif app == 'ha':
        return han_modules

def get_environment():
    """ Returns environment string; acc/prd"""
    env = run('env | grep ENVIRONMENT')
    print env
    if env:
        return env.replace('ENVIRONMENT=', '')

def get_application():
    """ Returns appie app name; nuffic, ha, etc. """
    app = run('env | grep APPLICATION')
    if app:
        return app.replace('APPLICATION=', '')

def get_instance_ports():
    """ Reads instance ports from buildout settings """
    env = get_environment()
    ports = run('cat ~/current/{0}-settings.cfg |grep "instance[0-9]-port"'.format(env))
    return [int(x.split('=')[1].lstrip()) for x in ports.replace('\r', '').split('\n')]

def fmt_date():
    now = datetime.now()
    return '{0}-{1}-{2}'.format(now.day, now.month, now.year)

def wget(url, retry=4, sleep=30):
    """ Multiple wget requests with a timeout """

    i = 0
    while i < retry:

        print '[{0}/{1}] Sleeping for {2} secs before trying'.format(i+1, retry, sleep)
        time.sleep(sleep)

        rv = run('wget -SO- -O /dev/null {}'.format(url), warn_only=True)

        if 'HTTP/1.1 200 OK' in rv:
            break

        i += 1

def replace_tag(tag, lines):
    last = lines[-1]

    if last.startswith('rev='):
        lines[-1] = 'rev={}'.format(tag)
    else:
        lines.append('rev={}'.format(tag))

    lines.append('\n')
    return ' '.join(lines)