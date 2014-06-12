import time
import re
from StringIO import StringIO
from ConfigParser import SafeConfigParser
from datetime import datetime
from fabric.api import cd, env, local, lcd, run, sudo, settings
from fabric.context_managers import settings
from fabric.operations import run
from fabric.state import env


def get_settings_file():
    appenv_info = env.deploy_info[env.appenv]
    parts = []

    parts.append("""
        [instance]
        username = {credentials[username]}
        password = {credentials[password]}
        user = {credentials[username]}:{credentials[password]}
    """.format(**appenv_info))

    for instance, port in appenv_info['ports']['instances'].items():
        parts.append("""
            [{instance}]
            http-address = {port}
        """.format(instance=instance, port=port))

    if 'varnish' in appenv_info['ports']:
        parts.append("""
            [varnish]
            port = {ports[varnish]}
        """.format(**appenv_info))

    if 'haproxy' in appenv_info['ports']:
        parts.append("""
            [haproxy-conf]
            port = {ports[haproxy]}
        """.format(**appenv_info))

    if 'zeo' in appenv_info['ports']:
        parts.append("""
            [zeo]
            zeo-address = {ipaddresses[flying-ip]}:{ports[zeo]}
            file-storage = {zeo-base}/filestorage/Data.fs
            blob-storage = {zeo-base}/blobstorage
        """.format(**appenv_info))

    for section, contents in appenv_info.get('buildout-parts', {}).items():
        part = "[{}]\n".format(section)
        for k, v in contents.items():
            part += "{} = {}\n".format(k,v)
        parts.append(part)

    part = "[cluster]\n"
    for k, v in appenv_info['ipaddresses'].items():
        part += "{} = {}\n".format(k,v)
    parts.append(part)

    text = '\n'.join(parts)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return StringIO(text)


def fmt_date():
    now = datetime.now()
    return now.strftime('%Y-%m-%d')


def wget(url, retry=4, sleep=30):
    """ Multiple wget requests with a timeout """
    for i in range(retry):
        rv = run('wget -SO- -O /dev/null {}'.format(url), warn_only=True)
        for expected_status in '200 OK', '404: Not Found':
            if expected_status in rv:
                return
        print '[{0}/{1}] Sleeping for {2} secs before trying'.format(
                i+1, retry, sleep)
        time.sleep(sleep)


def replace_tag(tag, lines):
    last = lines[-1]

    if last.startswith('rev='):
        lines[-1] = 'rev={}'.format(tag)
    else:
        lines.append('rev={}'.format(tag))

    lines.append('\n')
    return ' '.join(lines)


def check_for_existing_tag(tag, repo='.'):
    tags_output = local('( cd {} && git tag )'.format(repo), capture=True)
    return tag in tags_output.split()


def select_servers(func):
    def wrapped(layer='acc', server=None, *args, **kwargs):
        servers = env.deploy_info[layer]['hosts']
        cluster = get_master_slave(servers)
        if server:
            matches = [s for s in servers if server in s]
            if matches:
                servers = matches
            else:
                servers = [cluster[server]]
        for host in servers:
            print host
            is_master = host==cluster['master']
            with settings(host_string=host, appenv=layer, is_master=is_master):
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
