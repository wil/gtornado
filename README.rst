gtornado = gevent + Tornado
===========================


Introduction
------------

Tornado_ is a high performance web server and framework. It operates in a non-blocking fashion,
utilizing  Linux's epoll_ facility when available. It also comes bundled with several niceties
such as authentication via OpenID, OAuth, secure cookies, templates, CSRF protection and UI modules.

Unfortunately, some of its features ties the developer into its own asynchronous API implementation.

This module is an experiment to monkey patch it just enough to make it run under gevent_.
One advantage of doing so is that one can use a coroutine-style and code in a blocking fashion
while being able to use the tornado framework. For example, one could use Tornado's OpenID mixins, together with
other libraries (perhaps AMQP or XMPP clients?) that may not otherwise be written to Tornado's asynchronous API and therefore would block the entire process.

.. _Tornado: http://www.tornadoweb.org/
.. _epoll: http://www.kernel.org/doc/man-pages/online/pages/man4/epoll.4.html
.. _gevent: http://www.gevent.org/


Monkey Patching
---------------

gtornado currently includes patches to two different Tornado modules: ``ioloop`` and ``httpserver``.

The ``ioloop`` patch uses gevent's internal pyevent implementation, mapping ``ioloop``'s concepts
into libevent's.

The ``httpserver`` patch uses gevent's libevent_http wrapper, which *should* be blazing fast.
However, due to the way tornado's httpserver is structured, the monkey patching code has to do some,
well, monkeying around (parsing the headers from tornado and translating them into libevent_http calls.)
It tries to be fairly efficient, but if your application is doesn't do much (most benchmarks),
the parsing overhead can be a significant chunk of your CPU time.

There are two ways to monkey patch your tornado application:

- by importing the ``gtornado.monkey`` module and calling the ``patch_*`` functions in your tornado application source before importing any tornado modules.

::

  from gtornado.monkey import patch_all; patch_all()
  # now import your usual stuff
  from tornado import ioloop

- by running the gtornado.monkey module as a script, to let it patch tornado before running your tornado application.

::

  $ python -m gtornado.monkey my_tornado_app.py



