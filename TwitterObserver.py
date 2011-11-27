#!/usr/bin/env python

import os
import sys
import datetime
import cPickle
import ConfigParser
import optparse

import tweepy

_config = {}
DEBUG = False
RETRY_COUNT=0
RETRY_DELAY=0

TODAY=datetime.datetime.now().strftime("%Y-%m-%d")
YESTERDAY=(datetime.datetime.now() - datetime.timedelta(days = 1)).strftime("%Y-%m-%d")


def debug(msg):
    """Print debugging messages"""
    if DEBUG:
        print msg


def process_arguments():
    parser = optparse.OptionParser(version="%prog 0.1")
    parser.set_usage("%prog [options]\nObserve and report arbitrary Twitter" +
                      " users")
    parser.add_option('-c', '--config', dest='config',
                      default='~/.TwitterObserver.conf',
                      help='Config file path. Default: %default')
    parser.add_option('-d', '--debug', action='store_true', dest='debug',
                      help="Enable debugging output.")
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
    debug("Recording followers for @%s." % screen_name)
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
    api = tweepy.API(auth, secure=True, host="hozro.moo.cat")
    api.retry_count = RETRY_COUNT
    api.retry_delay = RETRY_DELAY
    # Retrieving id instead of screen_name in case a follower changes their
    # screen_name.
    followers_iter = tweepy.Cursor(api.followers, id=screen_name).items()
    followers = []
    debug("Receiving followers now.")
    for follower in followers_iter:
        followers.append(follower.id)
    debug("Done receiving followers.")
    # Sorting because sometimes Twitter returns followers in a different order
    debug("Sorting followers.")
    followers.sort()
    debug("Done sorting followers.")
    db_dir = os.path.join(_config.get('global', 'db_path'), screen_name)
    if not os.path.exists(db_dir):
        debug("Directory %s doesn't exist. Creating now." % db_dir)
        os.makedirs(db_dir)
    followers_file = os.path.join(db_dir, TODAY + ".p")
    debug("Writing followers to %s in pickle format." % followers_file)
    cPickle.dump(followers, open(followers_file, 'wb'))
    

def main():
    global DEBUG
    options = process_arguments()
    if options.debug: DEBUG = True
    load_config(options.config)
    for screen_name in _config.sections():
        if screen_name == "global":
            continue
        try:
            if _config.get(screen_name, 'followers') == 'yes':
                record_followers(screen_name)
        except ConfigParser.NoOptionError:
            pass


if __name__ == '__main__':
    main()
