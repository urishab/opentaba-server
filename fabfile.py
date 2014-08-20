"""
fab file for managing opentaba-server heroku apps
"""

from fabric.api import *
from request import get
from json import loads


@runs_once
def _heroku_connect():
    # this will either just show the user if connected or prompt for a connection
    # if a connection is not made it will error out and the fab process will stop
    local('heroku auth:whoami')


@runs_once
def _get_app_full_name(app_name):
    return 'opentaba-server-%s' % app_name


def _get_apps():
    # get the defined remotes' names, without 'origin' or 'all_apps'
    apps = ''.join(local('git remote', capture=True)).split('\n')
    if 'origin' in apps:
        apps.remove('origin')
    if 'all_apps' in apps:
        apps.remove('all_apps')
    
    return apps


def _download_gush_map(muni_name, topojson=False):
    r = get('http://raw.githubusercontent.com/niryariv/israel_gushim/master/%s.%s' % (muni_name, 'topojson' if topojson else 'geojson'))
    if r.status != 200:
        abort('Failed to download gushim map')
    
    try:
        res = loads(r.text)
    except:
        abort('Gushim map is an invalid JSON file')
    
    return res


@task
def create_app(app_name):
    """Create a new heroku app for a new municipality"""
    
    _heroku_connect()
    full_name = _get_app_full_name(app_name)
    
    # create a new heroku app with the needed addons
    local('heroku apps:create %s --addons scheduler:standard,memcachedcloud:25,mongohq:sandbox,redistogo:nano' % full_name)
    
    # get the new app's git url
    app_info = ''.join(local('heroku apps:info -s --app %s' % full_name, capture=True)).split('\n')
    app_git = None
    for i in app_info:
        if i[0:7] == 'git_url':
            app_git = i[8:]
            break
    
    if not app_git:
        delete_app(app_name, ignore_errors=True)
        abort('Something went wrong - couldn\'t parse heoku app\'s git url after creating it...')
    
    # add heroku app's repo as new remote
    local('git remote add %s %s' % (app_name, app_git))
    
    # add new remote to 'all_apps' remote so it's easy to push to all of the together
    with settings(warn_only=True):
        if local('git remote set-url --add all_apps %s' % app_git).failed:
            # in case just adding the the remote fails it probably doesn't exist yet, so try to add it
            if local('git remote add all_apps %s' % app_git).failed:
                delete_app(app_name, ignore_errors=True)
                abort('Could not add new remote to all_apps')
    
    # push code to the new app and create db and scrape for the first time
    deploy(app_name)
    renew_db(app_name)
    
    # add scheduled job - can't be done automatically
    print '*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*'
    print 'You must add a new scheduled job now to scrape data during every night'
    print 'This cannot be done automatically, but it\'s not hard. Just click "Add Job..."'
    print 'Command is: "python scrape.py -g all ; python worker.py" (without both "),'
    print '1X dyno, daily frequency, next run 04:00'
    print '*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*'
    local('heroku addons:open scheduler --app %s' % full_name)


@task
def delete_app(app_name, ignore_errors=False):
    """Delete a heroku app"""
    
    _heroku_connect()
    full_name = _get_app_full_name(app_name)
    
    with settings(warn_only=True):
        # try to find the app's git url if it is a remote here
        app_git = None
        remotes = ''.join(local('git remote -v', capture=True)).split('\n')
        for r in remotes:
            if r.startswith(app_name):
                app_git = r.split('\t')[1].split(' ')[0]
                break
        
        # delete remotes for taget app
        if app_git:
            local('git remote set-url --delete all_apps %s' % app_git, capture=ignore_errors)
        
        local('git remote remove %s' % app_name, capture=ignore_errors)
        
        # delete heroku app
        local('heroku apps:destroy --app %s --confirm %s' % (full_name, full_name), capture=ignore_errors)


@task
def add_gushim(muni_name, display_name):
    """Add the gush ids from an existing online gush map to the tools/gushim.py file"""
    
    # download the online gush map
    gush_map = _download_gush_map(muni_name)
    gush_ids = []
    
    # make a list of all gush ids in the file
    for geometry in gush_map['features']:
        gush_ids.append(geometry['properties']['Name'])
    
    # open and load the existing gushim dictionary from tools/gushim.py
    with open(os.path.join('tools', 'gushim.py')) as gushim_data:
        existing_gushim = loads(gushim_data.read())
    
    # remove all existing gushim from our new-gushim list, or create a new dictionary entry
    if muni_name in existing_gushim.keys():
        for eg in existing_gushim[muni_name]['list']:
            if eg in gush_ids:
                gush_ids.remove(eg)
    elif display_name == '':
        abort('For new municipalities display name must be provided')
    else:
        existing_gushim[muni_name] = {'display':'', 'list':[]}
    
    existing_gushim[muni_name]['display'] = display_name
    
    # append the remaining gush ids list
    if len(gush_ids) > 0:
        existing_gushim[muni_name]['list'] += gush_ids
    else:
        abort('No new gush ids were found in the downloaded gush map')
    
    # write the dictionary back to tools/gushim.py
    out = open(os.path.join('tools', 'gushim.py'), 'w')
    out.write('GUSHIM = ' + json.dumps(existing_gushim, sort_keys=True, indent=4, separators=(',', ': ')))
    out.close
    
    print '*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*'
    print 'The new gushim data was added to tools/gushim.py, but was not comitted.'
    print 'Please give the changes a quick look-see and make sure they look fine, then '
    print 'commit the changes and deploy your new/exisiting app.'
    print '*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*X*'


@task
def deploy(app_name):
    """Deploy changes to a certain heroku app"""
    
    local('git push %s master' % app_name)


@task
def deploy_all():
    """Deploy changes to all heroku apps"""
    
    local('git push all_apps master')


@task
def create_db(app_name):
    """Run the create_db script file on a certain heroku app"""
    
    _heroku_connect()
    full_name = _get_app_full_name(app_name)
    
    local('heroku run "python tools/create_db.py --force -m %s" --app %s' % (app_name, full_name))


@task
def update_db(app_name):
    """Run the update_db script file on a certain heroku app"""
    
    _heroku_connect()
    full_name = _get_app_full_name(app_name)
    
    local('heroku run "python tools/update_db.py --force -m %s" --app %s' % (app_name, full_name))


@task
def scrape_all(app_name, show_output=False):
    """Scrape all gushim on a certain heroku app"""
    
    _heroku_connect()
    full_name = _get_app_full_name(app_name)
    
    if show_output:
        local('heroku run "python scrape.py -g all; python worker.py" --app %s' % full_name)
    else:
        local('heroku run:detached "python scrape.py -g all; python worker.py" --app %s' % full_name)


@task
def renew_db(app_name):
    """Run the create_db script file and scrape all gushim on a certain heroku app"""
    
    create_db(app_name)
    scrape_all(app_name)


@task
def renew_db_all():
    """Run the create_db script file and scrape all gushim on all heroku apps"""
    
    for a in _get_apps():
        renew_db(a)


@task
def refresh_db(app_name):
    """Run the update_db script file and scrape all gushim on a certain heroku app"""
    
    update_db(app_name)
    scrape_all(app_name)


@task
def refresh_db_all():
    """Run the update_db script file and scrape all gushim on all heroku apps"""
    
    for a in _get_apps():
        update_db(a)