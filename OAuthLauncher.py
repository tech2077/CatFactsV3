from twisted.web import server, resource
from twisted.application import service, internet
from twisted.internet import ssl
from twisted.web.util import redirectTo
import CatFactsPush


class OAuthRedirector(resource.Resource):
    isLeaf = True
    factsStarted = False

    def render_GET(self, request):
        print(request.args)
        if b'access_token' in request.args.keys() and not self.factsStarted:
            print('Starting')
            self.factsStarted = True
            CatFactsPush.main(request.args[b'access_token'][0].decode())
            return b'<head><p>CatFacts Authenticated</p></head>'
        elif not self.factsStarted:
            return redirectTo(
                b'https://oauth.groupme.com/oauth/authorize?client_id=698dYmSqmHXVDKwHAaetmEKYMpb5ZsCDZQOza8V8k3wCtMPj',
                request)
        else:
            return b'<head><p>CatFacts Authenticated</p></head>'

site = server.Site(OAuthRedirector())

sslContext = ssl.DefaultOpenSSLContextFactory(
    '/etc/letsencrypt/live/nothingbuttheemptinessinyourheart.com/privkey.pem',
    '/etc/letsencrypt/live/nothingbuttheemptinessinyourheart.com/cert.pem')

application = service.Application("OAuth Service", gid=1, uid=1)
server = internet.SSLServer(443, site, contextFactory=sslContext)
server.setServiceParent(service.IServiceCollection(application))