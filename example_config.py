"""
Nuffic Fabric configuration, copy this file to config.py for local custimization.
"""
local_buildouts = dict(
    nuffic='/Users/leong/Projects/buildout-nuffic',
    ha='/Users/leong/Projects/buildout-nuffic-han'
)

buildout_tag = 'responsive'  # used in tasks:deploy_buildout
nuffic_modules = ('nuffic.theme', 'Products.NufficATContent')
han_modules = ('nuffic.theme', 'Products.NufficATContent', 'nuffic.han.content')