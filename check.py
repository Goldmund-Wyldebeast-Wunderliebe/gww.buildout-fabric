""" Specific Fabric tasks """

from fabric.api import env, run
from fabric.decorators import task
from .helpers import get_master_slave, select_servers


@task
def check_cluster(layer=None):
    """ Check HA/DRBD cluster health """
    if layer is None:
        layer = env.deploy_info['default']
    cluster = get_master_slave(env.deploy_info[layer]['hosts'], quiet=False)
    print('\n'.join(
        ['', 'Current cluster info for {0}:'.format(layer)] +
        ["\t{0} is {1}".format(k,v) for k,v in sorted(cluster.items())] +
        ['']))

@task
@select_servers
def test():
    """ Test if the connection is working """
    print(u'Testing {} {} connection for {}'.format(
        env.app, env.appenv, env.host_string))
    run('hostname ; whoami ; pwd')

