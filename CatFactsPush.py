import json, time
import groupy
import groupy.object
import requests
from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import WebSocketClientFactory, connectWS
from autobahn.twisted.websocket import WebSocketClientProtocol

DEBUG = False


def getFacts():
    """Get catfacts list from server and return list"""
    url = 'http://catfacts-api.appspot.com/api/facts'
    params = dict(number=10000)

    resp = requests.get(url=url, params=params)
    data = json.loads(resp.text)
    return data['facts']


def dprint(*args):
    """Condition print if debugging is enabled"""
    if DEBUG:
        print(args)


class PushClient(WebSocketClientProtocol):
    """Client class for GroupMe push client
    """
    def __init__(self):
        super().__init__()
        if DEBUG:
            txaio.start_logging(level='debug')
        # Setup necessary varibles for state machine
        # and groupme APIs
        self.facts = getFacts()
        self.id = 1
        self.push_state = 'None'
        self.user_id = groupy.User.get().user_id
        self.token = groupy.config.API_KEY
        self.client_id = ''
        self.last_ping = time.time()
        self.start_time = time.time()
        self.timeout = 0

    def onConnect(self, response):
        print("Connected")
        dprint(response)

    def onOpen(self):
        self.sendHandshake()
        self.push_state = 'handshake'                            # Set state machine
        dprint("Connected!")

    def onMessage(self, payload, isBinary):
        # Load received json into python dict
        message = json.loads(payload.decode('utf-8'))[0]
        # state machine
        if self.push_state == 'handshake':
            # If handshake sent, now subscribe to user channel
            dprint(message)
            self.client_id = message['clientId']                # Store client id for subscription
            self.timeout = message['advice']['timeout']/1000    # Timeout for client
            self.sendSubcribe()
            self.push_state = 'waiting'
        elif self.push_state == 'waiting':
            dprint(message)
            self.push_state = 'polling'                         # Switch to polling
        elif self.push_state == 'polling':
            dprint(message)
            # Filter out connect messages that occasionally occur
            if message['channel'] != '/meta/connect':
                data = message['data']
                # Take time of ping to ensure server has not ended connection
                if data['type'] == 'ping':
                    dprint(time.strftime("Ping: %m-%d-%Y %H:%M:%S"))
                    self.last_ping = time.time()
                elif data['type'] == 'subscribe':
                    dprint(message)
                    dprint('Retried')
                # If not ping, process data
                else:
                    contents = data['subject']

                    # Direct message send fact direct to user
                    if data['type'] == 'direct_message.create':
                        if contents['user_id'] != str(self.user_id):
                            # Get member object from id and send message through
                            m = groupy.object.responses.Member(user_id=contents['user_id'])
                            m.post("Did you know? {}".format(self.facts.pop(0)))

                    # Group message labeled as 'line.create'
                    elif data['type'] == 'line.create':
                        attachments = contents['attachments']
                        # Filter for mention of user, then reply to source of mention
                        for a in attachments:
                            if contents['user_id'] != str(self.user_id):
                                if a['type'] == 'mentions' and int(self.user_id) in [int(i) for i in a['user_ids']]:
                                    # Filter Cat Facts from user list
                                    users = [i for i in a['user_ids'] if int(i) != int(self.user_id)]
                                    # Get group that bot was mentioned in
                                    g = groupy.Group.list().filter(group_id__eq=contents['group_id'])[0]

                                    # Send Cat Fact to user or users listed
                                    if len(users) > 0:
                                        members = g.members()
                                        for u in users:
                                            m = members.filter(user_id__eq=str(u))[0]
                                            self.sendFacts(g, m.nickname, m.user_id)
                                    else:
                                        # Get caller username and id
                                        nickname = contents['name']
                                        user_id = contents['user_id']
                                        # Post formated mention of calling user
                                        self.sendFacts(g, nickname, user_id)
        else:
            print(message)

    def onClose(self, wasClean, code, reason):
        dprint("WebSocket connection closed: {0} {1}".format(reason, code))

    def onPing(self, payload):
        super().onPing(payload)
        dprint("Pinged: {}".format(payload))
        dprint(self.last_ping, time.time() - self.last_ping)
        # If groupme's "ping" takes longer than 30 seconds, reset connection
        if not (not (time.time() - self.last_ping > 30) and not (time.time() - self.start_time > self.timeout)):
            self.sendClose()

    def sendHandshake(self):
        """Send Handshake to push server"""
        handshake = {"channel": "/meta/handshake",
                     "version": "1.0",
                     "supportedConnectionTypes": ["websocket"],
                     "id": str(self.id)}
        self.sendMessage(json.dumps(handshake).encode('utf-8'))
        # Increment sending id, see GroupMe push api
        self.id += 1

    def sendSubcribe(self):
        """Subcribe to user channel on push server"""
        user_subcribe = {"channel": "/meta/subscribe",
                         "clientId": self.client_id,
                         "subscription": "/user/{}".format(self.user_id),
                         "id": str(self.id),
                         "ext": {"access_token": self.token,
                                 "timestamp": time.time()}
                         }
        self.sendMessage(json.dumps(user_subcribe).encode('utf-8'))
        # Increment sending id, see GroupMe push api
        self.id += 1

    def sendFacts(self, group, reciever_name, reciever_id):
        group.post("@{}: Did you know? {}".format(
            reciever_name, self.facts.pop(0)),
            groupy.attachments.Mentions([reciever_id],
                                        loci=[(0, 1 + len(reciever_name))]).as_dict())

    def sendMessage(self, payload, isBinary=False, fragmentSize=None,
                    sync=False, doNotCompress=False):
        super().sendMessage(payload, isBinary=False, fragmentSize=None,
                            sync=False, doNotCompress=False)
        dprint(payload)


class PushFactory(WebSocketClientFactory, ReconnectingClientFactory):
    """Factory to reconnect the push client after it's 10 minute timeout"""

    protocol = PushClient
    maxDelay = 0.1
    initialDelay = 0.1
    jitter = 0
    factor = 0

    def clientConnectionFailed(self, connector, reason):
        self.resetDelay()
        self.retry(connector)

    def clientConnectionLost(self, connector, unused_reason):
        self.resetDelay()
        self.retry(connector)


if __name__ == '__main__':
    if DEBUG:
        # Logging for twisted
        import txaio
        txaio.use_twisted()

    # Connect to server and start client factory
    factory = PushFactory(url="wss://push.groupme.com/faye")
    connectWS(factory, timeout=70)

    reactor.run()
