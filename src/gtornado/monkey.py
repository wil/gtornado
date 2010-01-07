import time
import cgi
import gevent
import gevent.hub
import gevent.http

def patch_tornado_ioloop():
    _tornado_iol = __import__('tornado.ioloop', fromlist=['fromlist_has_to_be_non_empty'])
    _IOLoop = _tornado_iol.IOLoop

    class IOLoop:
        READ  = _IOLoop.READ
        WRITE = _IOLoop.WRITE
        ERROR = _IOLoop.ERROR

        def __init__(self):
            self._handlers = {} # by fd
            self._events = {} # by fd

        def start(self):
            gevent.hub.get_hub().switch()

        def stop(self):
            for e,fd in list(self._events.iteritems()):
                self.remove_handler(e)

            gevent.hub.shutdown()

        def remove_handler(self, fd):
            self._handlers.pop(fd, None)
            ev = self._events.pop(fd, None)
            ev.cancel()

        def update_handler(self, fd, events):
            handler = self._handlers.pop(fd, None)
            self.remove_handler(fd)
            self.add_handler(fd, handler, events)

        def add_handler(self, fd, handler, events):
            type = gevent.core.EV_PERSIST
            if events & _IOLoop.READ:
                type = type | gevent.core.EV_READ
            if events & _IOLoop.WRITE:
                type = type | gevent.core.EV_WRITE
            if events & _IOLoop.ERROR:
                type = type | gevent.core.EV_READ

            def callback(ev, type):
                #print "ev=%r type=%r firing" % (ev, type)
                tornado_events = 0
                if type & gevent.core.EV_READ:
                    tornado_events |= _IOLoop.READ
                if type & gevent.core.EV_WRITE:
                    tornado_events |= _IOLoop.WRITE
                if type & gevent.core.EV_SIGNAL:
                    tornado_events |= _IOLoop.ERROR
                return handler(ev.fd, tornado_events)

            #print "add_handler(fd=%r, handler=%r, events=%r)" % (fd, handler, events)
            #print "type => %r" % type
            e = gevent.core.event(type, fd, callback)
            e.add()
            self._events[fd] = e
            self._handlers[fd] = handler


        def add_callback(self, callback):
            print "adding callback"
            gevent.spawn(callback)

        def add_timeout(self, deadline, callback):
            print "adding callback"
            gevent.spawn_later(int(deadline - time.time()), callback)

        @classmethod
        def instance(cls):
            if not hasattr(cls, "_instance"):
                print "new instance?"
                cls._instance = cls()
            return cls._instance

    #print "orig ioloop = ", dir(_tornado_iol)
    _tornado_iol.IOLoop = IOLoop
    #print "iol = ", id(_tornado_iol.IOLoop)



def patch_tornado_httpserver():
    from tornado.httpserver import HTTPRequest

    def parse_t_http_output(buf):
        headers, body = buf.split("\r\n\r\n", 1)
        headers = headers.split("\r\n")
        ver, code, msg = headers[0].split(" ", 2)
        code = int(code)
        chunked = False

        headers_out = []
        for h in headers[1:]:
            k, v = h.split(":", 1)
            if k == "Transfer-Encoding" and v == "chunked":
                chunked = True
            headers_out.append((k, v.lstrip()))

        return code, msg, headers_out, body, chunked

    def parse_post_body(req, body):
        content_type = req.headers.get("Content-Type", "")
        if req.method == "POST":
            if content_type.startswith("application/x-www-form-urlencoded"):
                arguments = cgi.parse_qs(req.body)
                for name, values in arguments.iteritems():
                    values = [v for v in values if v]
                    if values:
                        req.arguments.setdefault(name, []).extend(values)
            elif content_type.startswith("multipart/form-data"):
                boundary = content_type[30:]
                if boundary:
                    self._parse_mime_body(boundary, data)
                    # from HTTPConnection._parse_mime_body
                    if data.endswith("\r\n"):
                        footer_length = len(boundary) + 6
                    else:
                        footer_length = len(boundary) + 4
                    parts = data[:-footer_length].split("--" + boundary + "\r\n")
                    for part in parts:
                        if not part: continue
                        eoh = part.find("\r\n\r\n")
                        if eoh == -1:
                            logging.warning("multipart/form-data missing headers")
                            continue
                        headers = HTTPHeaders.parse(part[:eoh])
                        name_header = headers.get("Content-Disposition", "")
                        if not name_header.startswith("form-data;") or \
                           not part.endswith("\r\n"):
                            logging.warning("Invalid multipart/form-data")
                            continue
                        value = part[eoh + 4:-2]


                        name_values = {}
                        for name_part in name_header[10:].split(";"):
                            name, name_value = name_part.strip().split("=", 1)
                            name_values[name] = name_value.strip('"').decode("utf-8")
                        if not name_values.get("name"):
                            logging.warning("multipart/form-data value missing name")
                            continue
                        name = name_values["name"]
                        if name_values.get("filename"):
                            ctype = headers.get("Content-Type", "application/unknown")
                            req.files.setdefault(name, []).append(dict(
                                filename=name_values["filename"], body=value,
                                content_type=ctype))
                        else:
                            req.arguments.setdefault(name, []).append(value)


    class FakeStream():
        def __init__(self):
            self._closed = False

        def closed(self):
            print "stream closed = ", self._closed
            return self._closed


    class FakeConnection():
        def __init__(self, r):
            self._r = r
            self.xheaders = False
            self.reply_started = False
            self.stream = FakeStream()
            #r.connection.set_closecb(self)

        def _cb_connection_close(self, conn):
            print "connection %r closed!!!!" % (conn,)
            print "stream = %r" % self.stream
            self.stream._closed = True
            print "flagged stream as closed"

        def write(self, chunk):
            if not self.reply_started:
                #print "starting reply..."
                # need to parse the first line as RequestHandler actually writes the response line
                code, msg, headers, body, chunked = parse_t_http_output(chunk)

                for k, v in headers:
                    #print "header[%s] = %s" % (k, v)
                    self._r.add_output_header(k, v)

                if chunked:
                    self._r.send_reply_start(code, msg)
                    self._r.send_reply_chunk(body)
                else:
                    self._r.send_reply(code, msg, body)
                self.reply_started = True
            else:
                print "writing %s" % chunk
                self._r.send_reply_chunk(chunk)

        def finish(self):
            print "finishing..."
            self._r.send_reply_end()
            print "finished"


    class GHttpServer:
        def __init__(self, t_app):
            def debug_http_cb(r):
                print "http request = ", r
                for m in dir(r):
                    o = eval("r." + m)
                    if type(o) in (str, list, int, tuple):
                        print "r.%s = %r" % (m, o)
                r.add_output_header("X-Awesomeness", "100%")
                r.send_reply(200, "OK", '<b>hello</b>')


            def http_cb(r):
                body = r.input_buffer.read()
                treq = HTTPRequest(
                        r.typestr, # method
                        r.uri, # uri
                        headers=dict(r.get_input_headers()), # need to transform from list of tuples to dict
                        body=body,
                        remote_ip=r.remote_host,
                        protocol="http", # or https
                        host=None, # 127.0.0.1?
                        files=None, # ??
                        connection=FakeConnection(r))

                parse_post_body(treq, body)
                
                """
                print "http request = ", r
                for m in dir(r):
                    o = eval("r." + m)
                    if type(o) in (str, list, int, tuple):
                        print "r.%s = %r" % (m, o)
                """
                t_app(treq)

            self._httpserver = gevent.http.HTTPServer(http_cb)

        def listen(self, port):
            self._httpserver.serve_forever(('0.0.0.0', port), backlog=128)

        @classmethod
        def instance(cls):
            print "new instance?"
            if not hasattr(cls, "_instance"):
                cls._instance = cls()
            return cls._instance

    _httpserver = __import__('tornado.httpserver', fromlist=['fromlist_has_to_be_non_empty'])
    _httpserver.HTTPServer = GHttpServer


def patch_tornado():
    patch_tornado_ioloop()
    patch_tornado_httpserver()
