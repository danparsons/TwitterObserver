#!/usr/bin/env python

import os
import sys
import datetime
import json
import ConfigParser
import optparse

import tweepy

_config = {}
_report = {}
DEBUG = False
NOAPI = False
RETRY_COUNT=0
RETRY_DELAY=0

TODAY=datetime.datetime.now().strftime("%Y-%m-%d")
YESTERDAY=(datetime.datetime.now() -
          datetime.timedelta(days = 1)).strftime("%Y-%m-%d")


def debug(msg):
    """Print debugging messages"""
    if DEBUG:
        print msg


def report(screen_name, section, msg):
    """Handle filling out _report"""
    global _report
    if screen_name not in _report.keys():
        _report[screen_name] = {}
    if section not in _report[screen_name].keys():
        _report[screen_name][section] = ''
    else:
        _report[screen_name][section] += ', '
    _report[screen_name][section] += msg


def process_arguments():
    parser = optparse.OptionParser(version="%prog 0.1")
    parser.set_usage("%prog [options]\nObserve and report arbitrary Twitter" +
                      " users")
    parser.add_option('-c', '--config', dest='config',
                      default='~/.TwitterObserver.conf',
                      help='Config file path. Default: %default')
    parser.add_option('-d', '--debug', action='store_true', dest='debug',
                      help="Enable debugging output.")
    parser.add_option('-n', '--no-api', action='store_true', dest='noapi',
                      help='Disable Twitter API. Useful only for testing.')
    (options, args) = parser.parse_args()
    return options


def load_config(config_file):
    """Read config file with ConfigParser and store it in __config__"""
    global _config
    if not os.path.exists(config_file):
        print "ERROR: Config file %s not found." % config_file
        sys.exit(-1)
    config = ConfigParser.RawConfigParser()
    config.read(config_file)
    if 'global' not in config.sections():
        print "ERROR: [global] section not found in %s." % config_file
        sys.exit(-1)
    if not len(config.sections()) >= 2:
        print "ERROR: At least one [username] section required in config",
        print "file %s." % config_file
    _config = config


def record_followers(screen_name):
    """
    Retrieve followers for screen_name from Twitter and write them to disk.
    Will use request_token from [global] unless one is specified in [user].
    """
    debug("--- record_followers('%s')" % screen_name)
    if NOAPI:
        debug("Twitter API disabled. Returning.")
        return
    # If there is a request_token specified in the [user] section, then
    # use it. Otherwise, use the one from global.
    if (_config.has_option(screen_name, 'request_token_key') and
        _config.has_option(screen_name, 'request_token_secret')):
        debug("Using request_token from [%s] section." % screen_name)
        key = _config.get(screen_name, 'request_token_key')
        secret = _config.get(screen_name, 'request_token_secret')
    else:
        key = _config.get('global', 'request_token_key')
        secret = _config.get('global', 'request_token_secret')
    auth = tweepy.OAuthHandler('', '', secure=True)
    auth.set_request_token(key, secret)
    api = tweepy.API(auth, secure=True)
    api.retry_count = RETRY_COUNT
    api.retry_delay = RETRY_DELAY
    # Retrieving id instead of screen_name in case a follower changes their
    # screen_name.
    followers_iter = tweepy.Cursor(api.followers, id=screen_name).items()
    followers = {}
    debug("Receiving followers now.")
    for follower in followers_iter:
        followers[follower.id] = follower.screen_name
    debug("Done receiving followers.")
    db_dir = os.path.join(_config.get('global', 'db_path'), screen_name)
    if not os.path.exists(db_dir):
        debug("Directory %s doesn't exist. Creating now." % db_dir)
        os.makedirs(db_dir)
    followers_file = os.path.join(db_dir, TODAY + ".p")
    debug("Writing tweeps to %s in json format." % tweeps_file)
    fp = open(tweeps_file, 'w')
    fp.write(json.dumps(tweeps, sort_keys=True, indent=4))
    fp.close()
    hits_remaining = api.rate_limit_status()['remaining_hits']
    hits_reset_time = api.rate_limit_status()['reset_time']
    debug("%d API hits remaining. Resets at %s." % (hits_remaining,
          hits_reset_time))


def create_followers_delta(screen_name):
    """Compare today's followers for screen_name to yesterday's."""
    global _report
    lost_followers = []
    new_followers = []
    debug("--- create_followers_delta('%s')" % screen_name)
    debug("Comparing followers between %s and %s for %s." % (TODAY, YESTERDAY,
          screen_name))
    db_dir = os.path.join(_config.get('global', 'db_path'), screen_name)
    todays_followers_file = os.path.join(db_dir, TODAY + ".p")
    yesterdays_followers_file = os.path.join(db_dir, YESTERDAY + ".p")
    # Do we have followers recorded for today? If not, hit the API
    if not os.path.exists(todays_followers_file):
        record_followers(screen_name)
    # Do we have followers recorded for yesterday? If not, terminate.
    if not os.path.exists(yesterdays_followers_file):
        print "ERROR: Followers not found for %s on %s." % (screen_name,
                                                            YESTERDAY)
        return
    debug("Reading today's followers from disk.")
    debug("Reading yesterday's followers from disk.")
                                             'rb'))
    todays_followers = todays_followers_dict.keys()
    yesterdays_followers = yesterdays_followers_dict.keys()
    diff = list(set(yesterdays_followers) ^ set(todays_followers))
    todays_tweeps_dict = json.loads(open(todays_tweeps_file, 'r').read())
    yesterdays_tweeps_dict = json.loads(open(yesterdays_tweeps_file,
    for uid in diff:
        if uid not in todays_followers_dict.keys():
            lost_followers.append(uid)
        if not uid in yesterdays_followers_dict.keys():
            new_followers.append(uid)
    for uid in lost_followers:
        report(screen_name, 'Lost Followers', yesterdays_followers_dict[uid])
    for uid in new_followers:
        report(screen_name, 'New Followers', todays_followers_dict[uid])


def display_report():
    """Parse _report and display it"""
    for screen_name in _report:
        title = "Report for %s:" % screen_name
        bar = ""
        for x in range(len(title)):
            bar += '-'
        print title
        print bar
        for section in _report[screen_name]:
            print "%s: %s" % (section, _report[screen_name][section])
        print


def main():
    global DEBUG, NOAPI
    options = process_arguments()
    if options.debug:
        DEBUG = True
    if options.noapi:
        NOAPI = True
    load_config(options.config)
    for screen_name in _config.sections():
        if screen_name == "global":
            continue
        try:
            if _config.get(screen_name, 'followers') == 'yes':
                record_followers(screen_name)
            if _config.get(screen_name, 'followers_report') == 'delta':
                create_followers_delta(screen_name)
        except ConfigParser.NoOptionError:
            pass
    display_report()

if __name__ == '__main__':
    main()
