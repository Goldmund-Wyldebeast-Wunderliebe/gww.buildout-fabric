""" Shortcuts for running one or more tasks on a specific Nuffic environment
"""

from fabric.decorators import task, hosts
from tasks import pull_modules, restart_instances, prepare_release, deploy_buildout

@task
@hosts('app-nuffic-acc@46.22.180.90')
def acc_nuffic_update():
    """ Update Nuffic acceptance environment using pull_modules and
    restart_instances tasks.
    """
    pull_modules()
    restart_instances()

@task
@hosts('app-ha-acc@46.22.180.90')
def acc_ha_update():
    """ Update HAn acceptance environment using pull_modules
      and restart_instances tasks.
    """
    pull_modules()
    restart_instances()

@task
def prd_nuffic_release_tag():
    """ Locally tag modules for Nuffic prd env """
    prepare_release('nuffic')

@task
@hosts('app-nuffic-prd@46.22.180.89')
def prd_nuffic_release_deploy():
    """ Nuffic prd, deploy a new buildout in the releases directory """
    deploy_buildout()

@task
def prd_ha_release_tag():
    """ Locally tag modules for HAn prd env """
    prepare_release('ha')

@task
@hosts('app-ha-prd@46.22.180.89')
def prd_ha_release_deploy():
    """ HA prd, deploy a new buildout in the releases directory """
    deploy_buildout()