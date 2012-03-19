from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from wsgiproxy.exactproxy import proxy_exact_request
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.api import APIFactory
from repoze.who.classifiers import default_request_classifier
from repoze.who.classifiers import default_challenge_decider
from twofactor.models import DBSession, User
from pyramid.httpexceptions import HTTPFound
import time
import struct
import hmac
import hashlib
import base64


salt = 'sdks8d87uj33dfsf'


auth_tkt = AuthTktCookiePlugin('secret', 'auth_tkt')
identifiers = [('auth_tkt', auth_tkt)]
authenticators = [('auth_tkt', auth_tkt)]
challengers = []
mdproviders = []


def authenticate(secretkey, code_attempt):
    tm = int(time.time() / 30)

    secretkey = base64.b32decode(secretkey)

    # try 30 seconds behind and ahead as well
    for ix in [-1, 0, 1]:
        # convert timestamp to raw bytes
        b = struct.pack(">q", tm + ix)

        # generate HMAC-SHA1 from timestamp based on secret key
        hm = hmac.HMAC(secretkey, b, hashlib.sha1).digest()

        # extract 4 bytes from digest based on LSB
        offset = ord(hm[-1]) & 0x0F
        truncatedHash = hm[offset:offset + 4]

        # get the code from it
        code = struct.unpack(">L", truncatedHash)[0]
        code &= 0x7FFFFFFF
        code %= 1000000

        if ("%06d" % code) == str(code_attempt):
            return True

    return False


def notfound(request):
    return HTTPFound(location="/auth")


def auth(req):
    if req.method == "POST":
        name = req.params.get('username')
        code = req.params.get('code')
        user = DBSession.query(User).filter_by(username=name).all()
        if len(user) > 0:
            user = user[0]
            if authenticate(user.secret, code):
                creds = {}
                creds['repoze.who.userid'] = name
                creds['identifier'] = auth_tkt
                who_api = req.environ['who_api']
                headers = who_api.remember(creds)
                raise HTTPFound(location='/', headers=headers)
    return {'username': req.params.get('username', '')}


class Authenticator(object):

    def __init__(self, global_config, server, port, **settings):
        self.server = server
        self.port = port
        self.who = APIFactory(identifiers, authenticators, challengers,
            mdproviders, default_request_classifier, default_challenge_decider)
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)
        config = Configurator(settings=settings)
        config.add_route('auth', '/auth')
        config.add_view(auth, route_name='auth', renderer='templates/auth.pt')
        config.add_static_view(name='authstatic', path='twofactor:static')
        config.add_notfound_view(notfound, append_slash=True)
        self.pyramid = config.make_wsgi_app()

    def proxy(self, environ, start_response):
        environ['SERVER_NAME'] = self.server
        environ['SERVER_PORT'] = self.port
        return proxy_exact_request(environ, start_response)

    def __call__(self, environ, start_response):
        who_api = self.who(environ)
        environ['who_api'] = who_api
        if who_api.authenticate():
            return self.proxy(environ, start_response)
        else:
            return self.pyramid(environ, start_response)
