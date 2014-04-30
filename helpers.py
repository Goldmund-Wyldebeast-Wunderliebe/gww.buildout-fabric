import time
from datetime import datetime
from fabric.api import cd, env, local, lcd, run, sudo, settings

def get_modules():
    """ Returns Python get_modules for appie env """
    return env.modules

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

def get_instance_ports(old=False):
    """ Reads instance ports from buildout settings """
    env = get_environment()
    
    if not old:
        ports = run('cat ~/current/{0}-settings.cfg | grep -v "^#" | grep -A1 "instance[0-9]" | grep http-address'.format(env))
    else:
        ports = run('cat ~/current/{0}-settings.cfg | grep -v "^#" | grep "instance[0-9]-port"'.format(env))

    return [int(x.split('=')[1].lstrip()) for x in ports.replace('\r', '').split('\n')]

def fmt_date():
    now = datetime.now()
    return now.strftime('%Y-%m-%d')

def wget(url, retry=4, sleep=30):
    """ Multiple wget requests with a timeout """

    i = 0
    while i < retry:

        rv = run('wget -SO- -O /dev/null {}'.format(url), warn_only=True)
        if '200 OK' in rv:
            break

        print '[{0}/{1}] Sleeping for {2} secs before trying'.format(i+1, retry, sleep)
        time.sleep(sleep)
        i += 1

def replace_tag(tag, lines):
    last = lines[-1]

    if last.startswith('rev='):
        lines[-1] = 'rev={}'.format(tag)
    else:
        lines.append('rev={}'.format(tag))

    lines.append('\n')
    return ' '.join(lines)

def check_for_existing_tag(tag):
    tags_output = local('git tag'.format(tag), capture=True)
    tags = tags_output.split('\n')  

    if tag in tags:
        return True




    