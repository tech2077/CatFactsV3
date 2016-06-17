import json, time
import groupy
import groupy.object
from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.twisted.websocket import WebSocketClientFactory, connectWS
from autobahn.twisted.websocket import WebSocketClientProtocol


class GroupMeBot(WebSocketClientProtocol):
    """Client class for GroupMe push client
    """
    def __init__(self):
        # Setup necessary varibles for state machine
        # and groupme APIs
        self.id = 1
        self.token = None
        self.user_id = None
        self.push_state = 'None'
        self.client_id = ''
        self.last_ping = time.time()
        self.start_time = time.time()
        self.timeout = 0
        super().__init__()

    def onConnect(self, response):
        if self.factory.debug:
            import txaio
            txaio.use_twisted()
            txaio.start_logging(level='debug')

        print("Connected")

        self.user_id = groupy.User.get().user_id
        if self.factory.api_key is not None:
            groupy.config.API_KEY = self.factory.api_key
            self.token = groupy.config.API_KEY
        self.log.info(response)

    def onOpen(self):
        self.sendHandshake()
        self.push_state = 'handshake'                            # Set state machine
        self.log.debug("Connected!")

    def onGroupMessage(self, contents):
        """Group message callback"""
        pass

    def onDirectMessage(self, contents):
        """Direct message callback"""
        pass

    def onMessage(self, payload, isBinary):
        # Load received json into python dict
        message = json.loads(payload.decode('utf-8'))[0]
        # state machine
        if self.push_state == 'handshake':
            # If handshake sent, now subscribe to user channel
            self.log.debug(message)
            self.client_id = message['clientId']                # Store client id for subscription
            self.timeout = message['advice']['timeout']/1000    # Timeout for client
            self.sendSubcribe()
            self.push_state = 'waiting'
        elif self.push_state == 'waiting':
            self.log.info(message)
            self.push_state = 'polling'                         # Switch to polling
        elif self.push_state == 'polling':
            self.log.info(message)
            # Filter out connect messages that occasionally occur
            if message['channel'] != '/meta/connect':
                data = message['data']
                # Take time of ping to ensure server has not ended connection
                if data['type'] == 'ping':
                    self.log.debug(time.strftime("Ping: %m-%d-%Y %H:%M:%S"))
                    self.last_ping = time.time()
                elif data['type'] == 'subscribe':
                    self.log.debug(message)
                    self.log.debug('Retried')
                # If not ping, process data
                else:
                    contents = data['subject']

                    # Direct message send fact direct to user
                    if data['type'] == 'direct_message.create':
                        self.onDirectMessage(contents)

                    # Group message labeled as 'line.create'
                    elif data['type'] == 'line.create':
                        self.onGroupMessage(contents)
        else:
            print(message)

    def onClose(self, wasClean, code, reason):
        self.log.debug("WebSocket connection closed: {0} {1}".format(reason, code))

    def onPing(self, payload):
        """Callback for socket ping"""
        super().onPing(payload)
        self.log.debug("Pinged: {}".format(payload))
        self.log.debug(self.last_ping, time.time() - self.last_ping)
        # If groupme's "ping" takes longer than 32 seconds, reset connection
        if not (not (time.time() - self.last_ping > 32) and not (time.time() - self.start_time > self.timeout)):
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

    def sendMessage(self, payload, isBinary=False, fragmentSize=None,
                    sync=False, doNotCompress=False):
        """debug wrapper for """
        super().sendMessage(payload, isBinary=False, fragmentSize=None,
                            sync=False, doNotCompress=False)
        self.log.debug(payload, self.DEBUG)


class GroupMeBotFactory(WebSocketClientFactory, ReconnectingClientFactory):
    """Factory to reconnect the push client after it's 10 minute timeout"""
    maxDelay = 0.1
    initialDelay = 0.1
    jitter = 0
    factor = 0

    def __init__(self, *args, **kwargs):
        self.api_key = kwargs.pop('api_key', None)
        self.debug = kwargs.pop('DEBUG', None)
        super().__init__(*args, **kwargs)

    def clientConnectionFailed(self, connector, reason):
        self.resetDelay()
        self.retry(connector)

    def clientConnectionLost(self, connector, unused_reason):
        self.resetDelay()
        self.retry(connector)