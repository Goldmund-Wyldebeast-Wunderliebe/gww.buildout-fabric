import time
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from fabric.api import env, local, run, settings, get
from fabric.contrib.files import exists
import os
import StringIO
from ConfigParser import ConfigParser


def config_template(filename, appenv_info):
    appenv_info.update(env=env.app, appenv=env.appenv, now=datetime.now())
    templates = env.deploy_info.get('templates', ['templates'])
    jinja_env = Environment(loader=FileSystemLoader(templates))
    template = jinja_env.get_template(filename)
    return template.render(appenv_info)

def read_remote_config_files(appenv_info):
    """ Grab configuration files from remote host """
    config_map = appenv_info.get('remote_configs')
    if not config_map:
        return {}
    for config_name, file_name in config_map.items():
        if not exists(file_name):
            continue
        run('ls -l ' + file_name)
        config_file = StringIO.StringIO()
        get('clockuser.cfg', local_path=config_file)
        config_file.seek(0)
        config = ConfigParser()
        config.readfp(config_file)
        result = {}
        for section in config.sections():
            result[section] = dict(config.items(section))
        appenv_info[config_name] = result


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


def select_servers(func):
    def wrapped(layer=None, server=None, *args, **kwargs):
        if layer is None:
            layer = env.deploy_info['default']
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

