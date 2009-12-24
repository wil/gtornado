gtornado = Tornado + gevent
===========================

:Author: Wil Tan
:Version: $Revision: 


Introduction
------------

Tornado_ is a high performance web server and framework. It operates in a non-blocking fashion,
utilizing  Linux's epoll_ facility when available. It also comes bundled with several niceties
such as authentication via OpenID, OAuth, secure cookies, templates, CSRF protection and UI modules.

Unfortunately, some of its features ties the developer into its own asynchronous API implementation.

This module is an experiment to monkey patch it just enough to make it run under gevent.
One advantage of doing so is that one can use a coroutine-style and code in a blocking fashion
while being able to use the tornado framework.

.. _Tornado: http://www.tornadoweb.org/
.. _epoll: http://www.kernel.org/doc/man-pages/online/pages/man4/epoll.4.html
