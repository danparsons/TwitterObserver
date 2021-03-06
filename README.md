TwitterObserver
===============
TwitterObserver is a tool for recording and reporting on arbitrary Twitter
users.

It's designed to be run from cron once per day. It will record a user's
followers, friends and other stuff to disk and then tell you what the
differences are between right now and yesterday, via email, web report 
and Twitter DMs. In this way, you can see who stopped following you, who
started following you, etc.

The design allows for scanning multiple users (not just yourself) and from 
multiple points of view (different oAuth sessions, different HTTP proxies.)

Features
========
* Silent block detection (check if a user is blocking you, without them noticing)
* Report on mutual followers / friends
* Report on who has RT'd a user, and how often

Requirements
============
* Tweepy. 'easy_install tweepy' should take care of it.
* Your own Twitter oAuth request token key & secret. I'll write clear docs on how to get this soon. Until then, see this URL: https://dev.twitter.com/docs/auth

Known limitations
=================
* Not all features are implemented yet. I just started! I'll write usage docs when the tool is more complete. For now, look at -h and example_config.conf.
* Due to Twitter's pagination and API rate limiting, you can easily run out of API requests when scanning a user with a lot of followers. You get 150 API calls per hour, and Twitter returns only 100 followers per call.

Credits
=======
* Joshua Roesslein for making the awesome tweepy library.
* A bunch of jerks from Montreal, QC for inspiring some of TwitterObserver's features :)
