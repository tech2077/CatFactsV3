from twisted.web import server, resource
from twisted.internet import reactor, ssl
from twisted.web.util import redirectTo
import CatFactsPush


class Simple(resource.Resource):
    isLeaf = False

    def render_GET(self, request):
        print(request.args)
        if 'access_token' in request.args.keys():
            CatFactsPush.main(request.args['access_token'])
            return b"<head><p>CatFacts Authenticated</p></head>"
        else:
            return redirectTo(
                b"https://oauth.groupme.com/oauth/authorize?client_id=698dYmSqmHXVDKwHAaetmEKYMpb5ZsCDZQOza8V8k3wCtMPj",
                request)

site = server.Site(Simple())

sslContext = ssl.DefaultOpenSSLContextFactory(
    '/etc/letsencrypt/live/nothingbuttheemptinessinyourheart.com/privkey.pem',
    '/etc/letsencrypt/live/nothingbuttheemptinessinyourheart.com/cert.pem')

reactor.listenSSL(443, site, contextFactory=sslContext)
reactor.run()
