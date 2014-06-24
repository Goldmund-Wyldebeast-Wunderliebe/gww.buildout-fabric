""" Specific Fabric tasks """

from datetime import datetime
import os

from fabric.api import env, local, lcd
from fabric.decorators import task


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



################
# Basic tasks
################

@task
def prepare_release(tag=None):
    """ Git tag all modules in env.modules, pin tags in prd-sources.cfg and tag buildout """

    if not tag:
        now = datetime.now()
        tag = '{}-{}'.format(env.appenv, now.strftime('%Y-%m-%d'))

    def git_tag(tag):
        # XXX why commit? and why tag -f?
        local('git commit -am "tagging production release"')
        local('git tag -af {} -m "tagged production release"'.format(tag))
        local('git push --tags -f')
        local('git push')

    modules = env.modules

    existing_tag = False
    if check_for_existing_tag(tag):
        print('Buildout already tagged with tag {0}'.format(tag))
        existing_tag = True
    for m in modules:
        srcdir = os.path.join('src', m)
        if check_for_existing_tag(tag, repo=srcdir):
            print('Git module {0} already tagged with tag {1}'.format(m, tag))
            existing_tag = True
    if existing_tag:
        return  # don't reuse tag

    for m in modules:
        srcdir = os.path.join('src', m)
        if not check_for_existing_tag(tag, repo=srcdir):
            with lcd(srcdir):
                #local('''sed -i.org 's/version = .*/version = "{}"/' setup.py'''.format(tag))
                # XXX Modify version in setup.py if we intend jarn.mkrelease,
                # and tag is like "1.1.5".  That only makes sense on a single
                # module, not in this case.
                # If tag is something like "sprint7", we dont' modify the
                # module, just add a tag.
                git_tag(tag)
                print('Tagged git module {0} with tag {1}'.format(m, tag))

    old_settings = 'prd-sources.cfg'
    new_settings = 'prd-sources.cfg.new'

    if not os.path.isfile(old_settings):    
        print(
            '\nCannot set tags in prd-settings.cfg, add your git module '
            '(ending with rev=dummy) to this config.'
        )
        raise

    local('touch {}'.format(new_settings))

    print('\nChanging tags in prd-settings.cfg, make sure your module is in prd-settings.cfg.')
    with open(new_settings, 'wt') as fout:
        with open(old_settings, 'rt') as fin:
            for line in fin:
                lines = line.split()

                if tag in line:
                    print('Git module {0} already pinned, skipping.')
                    continue

                if lines[0] in modules:
                    line = replace_tag(tag, lines)

                fout.write(line)

    local('cp {0} {0}.old'.format(old_settings))
    local('mv {0} {1}'.format(new_settings, old_settings))

    if not check_for_existing_tag(tag):
        git_tag(tag)
        print('Tagged buildout with tag {0}'.format(tag))

