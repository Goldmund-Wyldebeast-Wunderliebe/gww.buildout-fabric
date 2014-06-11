import time
import re
from StringIO import StringIO
from ConfigParser import SafeConfigParser
from datetime import datetime
from fabric.api import cd, env, local, lcd, run, sudo, settings
from fabric.context_managers import settings
from fabric.operations import run
from fabric.state import env


def get_modules():
    """ Returns Python get_modules for appie env """
    return env.modules

def get_config():
    """ Reads all kinds of stuff from buildout settings """
    if hasattr(env, 'config'):
        return env.config
    filename = '~/current/{0}-settings.cfg'.format(env.appenv)
    buf = StringIO(run('cat ' + filename, quiet=True))
    env.config = SafeConfigParser()
    env.config.readfp(buf, filename)
    return env.config

def get_instance_ports():
    """ Reads instance ports from buildout settings """
    config = get_config()
    return [
            int(v)
            for s in sorted(config.sections())
            for k, v in sorted(config.items(s))
            if re.match('instance\d$',s) and k=='http-address'
            or re.match('instance\d-port$',k)
           ]

def get_zodb_paths():
    config = get_config()
    return {
            k: v
            for k, v in config.items('zeo')
            if re.match('(file|blob)-storage$',k)
           }

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


def select_servers(func):
    def wrapped(layer='acc', server=None, *args, **kwargs):
        servers = env.deploy_info[layer]['hosts']
        if server:
            matches = [s for s in servers if server in s]
            if matches:
                servers = matches
            else:
                cluster = get_master_slave(servers)
                servers = [cluster[server]]
        for host in servers:
            print host
            with settings(host_string=host, appenv=layer):
                func(*args, **kwargs)
    wrapped.__name__ = func.__name__
    wrapped.__doc__ = func.__doc__
    return wrapped


def test_connection():
    """ Task to test if the connection is working """

    print(u'Testing fabric connection for {0}'.format(env.host_string))
    run('hostname ; whoami ; pwd')


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
