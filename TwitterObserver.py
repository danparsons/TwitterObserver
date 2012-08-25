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
RETRY_COUNT=10
RETRY_DELAY=5
FORCE_DOWNLOAD = False

TODAY=datetime.datetime.now().strftime("%Y-%m-%d")
YESTERDAY=(datetime.datetime.now() -
          datetime.timedelta(days = 1)).strftime("%Y-%m-%d")

VALID_TWEEP_TYPES = ['followers', 'friends', 'favorites']


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
        if 'favorites' in section:
            _report[screen_name][section] += "\n"
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
    parser.add_option('-f', '--force-download', action='store_true', dest='force_download', help="Force tweep download, even if data already exists for today")
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


def record_tweeps(screen_name, tweep_type):
    """
    Retrieve followers for screen_name from Twitter and write them to disk.
    Will use access_token from [global] unless one is specified in [user].
    """
    if tweep_type not in VALID_TWEEP_TYPES:
        print "ERROR: parameter tweep_type for record_tweeps() must be one of",
        print VALID_TWEEP_TYPES
        return
    debug("--- record_tweeps('%s', '%s')" % (screen_name, tweep_type))
    if NOAPI:
        debug("Twitter API disabled. Returning.")
        return
    # If there is a access_token specified in the [user] section, then
    # use it. Otherwise, use the one from global.
    if (_config.has_option(screen_name, 'access_token_key') and
        _config.has_option(screen_name, 'access_token_secret')):
        debug("Using access_token from [%s] section." % screen_name)
        key = _config.get(screen_name, 'access_token_key')
        secret = _config.get(screen_name, 'access_token_secret')
    else:
        key = _config.get('global', 'access_token_key')
        secret = _config.get('global', 'access_token_secret')
    auth = tweepy.OAuthHandler('', '', secure=True)
    debug("Using access_token_key: %s" % key)
    debug("Using access_token_secret: %s" % secret)
    auth.set_access_token(key, secret)
    if (key == '') or (secret == ''):
        print "ERROR: access_token_key and access_token_secret cannot",
        print "be blank."
        sys.exit(-1)
    if key == "None":
        debug("Using no authentication")
        api = tweepy.API()
    else:
        api = tweepy.API(auth, secure=True)
    api.retry_count = RETRY_COUNT
    api.retry_delay = RETRY_DELAY
    # Retrieving id instead of screen_name in case a tweep changes their
    # screen_name.
    if tweep_type == "followers":
        tweeps_iter = tweepy.Cursor(api.followers, id=screen_name).items()
    if tweep_type == "friends":
        tweeps_iter = tweepy.Cursor(api.friends, id=screen_name).items()
    if tweep_type == "favorites":
        tweeps_iter = tweepy.Cursor(api.favorites, id=screen_name).items()
    tweeps = {}
    db_dir = os.path.join(_config.get('global', 'db_path'), screen_name)
    tweeps_file = os.path.join(db_dir, TODAY + "." + tweep_type + ".json")
    if os.path.exists(tweeps_file):
    if os.path.exists(tweeps_file) and FORCE_DOWNLOAD != False:
        debug("%s exists, skipping downloading tweeps for %s." % (tweeps_file, screen_name))
        return
    debug("Receiving tweeps now.")
    for tweep in tweeps_iter:
        if tweep_type == "favorites":
            _msg = '@%s: "%s" at %s. RTd %s time(s).' % \
                   (tweep.author.screen_name,
                    tweep.text,
                    tweep.created_at,
                    tweep.retweet_count)
            tweeps[tweep.id] = _msg
        else:
            tweeps[tweep.id] = tweep.screen_name
    debug("Done receiving tweeps.")
    if not os.path.exists(db_dir):
        debug("Directory %s doesn't exist. Creating now." % db_dir)
        os.makedirs(db_dir)
    debug("Writing tweeps to %s in json format." % tweeps_file)
    fp = open(tweeps_file, 'w')
    fp.write(json.dumps(tweeps, sort_keys=True, indent=4))
    fp.close()
    hits_remaining = api.rate_limit_status()['remaining_hits']
    hits_reset_time = api.rate_limit_status()['reset_time']
    debug("%d API hits remaining. Resets at %s." % (hits_remaining,
          hits_reset_time))


def create_tweeps_delta(screen_name, tweep_type):
    """Compare today's followers for screen_name to yesterday's."""
    global _report
    if tweep_type not in VALID_TWEEP_TYPES:
        print "ERROR: parameter tweep_type for create_tweeps_delta() must",
        print "be one of ",
        print VALID_TWEEP_TYPES
        return
    lost_tweeps = []
    new_tweeps = []
    debug("--- create_tweeps_delta('%s', '%s')" % (screen_name, tweep_type))
    debug("Comparing %s between %s and %s for %s." % (tweep_type, TODAY,
          YESTERDAY, screen_name))
    db_dir = os.path.join(_config.get('global', 'db_path'), screen_name)
    todays_tweeps_file = os.path.join(db_dir, TODAY + "." +
                                      tweep_type + ".json")
    yesterdays_tweeps_file = os.path.join(db_dir, YESTERDAY + "." +
                                          tweep_type + ".json")
    # Do we have tweeps recorded for today? If not, hit the API
    if not os.path.exists(todays_tweeps_file):
        record_tweeps(screen_name, tweep_type)
    # Do we have tweeps recorded for yesterday? If not, terminate.
    if not os.path.exists(yesterdays_tweeps_file):
        print "ERROR: %s not found for %s on %s." % (tweep_type, screen_name,
                                                            YESTERDAY)
        return
    debug("Reading today's tweeps from disk.")
    todays_tweeps_dict = json.loads(open(todays_tweeps_file, 'r').read())
    debug("Reading yesterday's tweeps from disk.")
    yesterdays_tweeps_dict = json.loads(open(yesterdays_tweeps_file,
                                           'r').read())
    todays_tweeps = todays_tweeps_dict.keys()
    yesterdays_tweeps = yesterdays_tweeps_dict.keys()
    diff = list(set(yesterdays_tweeps) ^ set(todays_tweeps))
    for uid in diff:
        if uid not in todays_tweeps_dict.keys():
            lost_tweeps.append(uid)
        if not uid in yesterdays_tweeps_dict.keys():
            new_tweeps.append(uid)
    for uid in lost_tweeps:
        report(screen_name, 'Lost %s' % tweep_type,
               yesterdays_tweeps_dict[uid])
    for uid in new_tweeps:
        report(screen_name, 'New %s' % tweep_type, todays_tweeps_dict[uid])


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
            if 'favorites' in section:
                msg = "%s:\n%s\n" % (section, _report[screen_name][section])
            else:
                msg = "%s: %s\n" % (section, _report[screen_name][section])
            print msg.encode("UTF-8")
        print "\n"


def main():
    global DEBUG, NOAPI
    options = process_arguments()
    if options.debug:
        DEBUG = True
    if options.noapi:
        NOAPI = True
    if options.force_download:
        FORCE_DOWNLOAD = True
    load_config(options.config)
    for screen_name in _config.sections():
        if screen_name == "global":
            continue
        try:
            if _config.get(screen_name, 'followers') == 'yes':
                record_tweeps(screen_name, 'followers')
            if _config.get(screen_name, 'followers_report') == 'delta':
                create_tweeps_delta(screen_name, 'followers')
            if _config.get(screen_name, 'friends') == 'yes':
                record_tweeps(screen_name, 'friends')
            if _config.get(screen_name, 'friends_report') == 'delta':
                create_tweeps_delta(screen_name, 'friends')
            if _config.get(screen_name, 'favorites') == 'yes':
                record_tweeps(screen_name, 'favorites')
            if _config.get(screen_name, 'favorites_report') == 'delta':
                create_tweeps_delta(screen_name, 'favorites')
        except ConfigParser.NoOptionError:
            pass
    # Have we already displayed a report today?
    reported_file = os.path.join(_config.get('global', 'db_path'), TODAY)
    if os.path.exists(reported_file):
        debug("Already reported today, exiting")
        sys.exit(0)
    fp = open(reported_file, 'w')
    fp.close()
    display_report()

if __name__ == '__main__':
    main()
