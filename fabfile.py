from fabric.api import env

from tasks import *
from shortcuts import *

env.subsite_urls = dict(
    nuffic='http://localhost:{0}/nuffic-site/nuffic/',
    ha='http://localhost:{0}/nuffic-han/www.hollandalumni.nl/'
)

env.buildouts = dict(
    nuffic='git@git.gw20e.com:Nuffic/buildout-nuffic.git',
    ha='git@git.gw20e.com:Nuffic/buildout-nuffic-han.git'
)

