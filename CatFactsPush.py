import requests, json, groupy
from GroupMeBot import GroupMeBot, GroupMeBotFactory
from twisted.internet import reactor
from autobahn.twisted.websocket import connectWS


def getFacts():
    """Get catfacts list from server and return list"""
    url = 'http://catfacts-api.appspot.com/api/facts'
    params = dict(number=10000)

    resp = requests.get(url=url, params=params)
    data = json.loads(resp.text)
    return data['facts']


class CatFactsBot(GroupMeBot):
    def __init__(self):
        super().__init__()
        self.facts = getFacts()

    def onDirectMessage(self, contents):
        if contents['user_id'] != str(self.user_id):
            # Get member object from id and send message through
            m = groupy.object.responses.Member(user_id=contents['user_id'])
            m.post("Did you know? {}".format(self.facts.pop(0)))

    def onGroupMessage(self, contents):
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

    def sendFacts(self, group, reciever_name, reciever_id):
        """Send catfacts to person on group"""
        group.post("@{}: Did you know? {}".format(
            reciever_name, self.facts.pop(0)),
            groupy.attachments.Mentions([reciever_id],
                                        loci=[(0, 1 + len(reciever_name))]).as_dict())

if __name__ == '__main__':
    # Connect to server and start client factory
    factory = GroupMeBotFactory(url="wss://push.groupme.com/faye", protocol=GroupMeBot)
    factory.protocol = CatFactsBot
    connectWS(factory, timeout=70)

    reactor.run()
