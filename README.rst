Nuffic tools
============

This module contains a Fabric script with several functions for releasing and
deploying to Nuffic acceptance and production.

Bootstrapping Fabric
--------------------

To get started with Fabric first we need virtualenv, we will create one in the
nuffic-tools directory

    # virtualenv .

Activate virtualenv and install requirements via Pip

    # . ./bin/activate

    # pip install -r requirements.txt

Create config file, used for storing active Python modules and local buildout
paths.

    # cp example_config.py config.py

    # vim config.py  # Adjust config to your local environment

Add your SSH public key to the remote appie user, see paragraph 'Prepairing
Nuffic Appie environments'  below.


Fabric shortcuts
----------------
Shortcuts for running one or more tasks on a specific Nuffic environment

Usage: fab  <task name>

Examples:

Update Nuffic acceptance

    # fab acc_nuffic_update 

acc_nuffic_update
    Update Nuffic acceptance environment using *pull_modules* and
    *restart_instances* tasks.

acc_ha_update
    Update Holland Alumni network acceptance environment using *pull_modules*
    and *restart_instances* tasks.

prd_nuffic_release_tag
    Tag git modules in local Nuffic buildout for deployment

prd_nuffic_release_deploy
    Deploy a new buildout in the releases directory for app-nuffic-prd

prd_ha_release_tag
    Tag git modules in local HA buildout for deployment

prd_ha_release_deploy
    Deploy a new buildout in the releases directory for app-ha-prd


Fabric tasks
------------

Usage: fab -H <remote host> -u <appie user> <task name>

Examples:

Restart connection on nuffic-acc:
    # fab -H nuffic-acc -u app-nuffic-acc restart_instances

Prepare production release locally:
    # fab -H prepare_release:nuffic

test_connection
    Runs a few harmless commands on the remote server to check the connection

pull_modules
    Used on acceptance to pull Git development modules.

restart_instances
    Restarts all instances in the remote buildout. After restarting an instance
    the script waits until the instance is up, it then continues restarting
    other instances.

prepare_release:<app-env>
    Adds production git tag to active Python modules, and configures prd-sources
    with same git tag.

    This is a local task, no remote host or user is needed!

deploy_buildout
    This script handles the steps (1) which are executed on the production Appie's
    to deploy a new buildout. A fresh buildout is cloned and run. Switching can 
    be done in the next task.

switch_buildout
    The current buildout will be switched with the new one. Instances are restarted 
    and finally a switch is made between the old buildout and the  new one.

1. https://intranet.gw20e.com/projects/nuffic/new-prd-release


Prepairing Nuffic Appie environments
------------------------------------

All Nuffic portals are contained in Appie environments. Appie users are
'locked' accounts by default. If a user is locked two exclamation marks can
be seen in /etc/shadow

This user is locked:

    # sudo cat /etc/shadow | grep app-nuffic-acc

    app-nuffic-acc:!!:15558:0:99999:7:::

Unlock the user:

    # sudo passwd -f -u app-nuffic-acc

Now we need to add your SSH public key to the authorized keys of the appie
user. If no .ssh directory of authorized_keys file is present create the ssh
dir structure by hand. Please keep in mind file permissions on ssh dir/files
must not be world/group readable and writeable.

    # appie become nuffic acc

    # vi .ssh/authorized_keys  # Add your public key

Now check if you connect via SSH:

    # ssh app-nuffic-acc@nuffic-acc

If the SSH connection is working, Fabric is also working. Use the following
command to double check:

    # fab -H nuffic-acc -u app-nuffic-acc test_connection

