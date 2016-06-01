import groupy, time

# Test account token location
groupy.config.KEY_LOCATION = './test_token'

# Read token in
with open(groupy.config.KEY_LOCATION, "r") as f:
    groupy.config.API_KEY = f.read()

# Read owner id from file
owner_id = ''
with open('./owner_id', "r") as f:
    owner_id = f.read()

online = True

while online:
    print('Start Test')

    # Find catfacts user from members and add to test group
    mlists = groupy.Member.list()
    print(mlists)
    m = mlists.filter(nickname__contains='Cat')[0]
    g = groupy.Group.create('TestV3')
    g.add(m)

    time.sleep(1)

    # Send test message
    g.post('@Cat Facts', groupy.attachments.Mentions([m.user_id], loci=[(0, 10)]).as_dict())

    time.sleep(2)

    # List of messages in test group
    ms = g.messages()

    # If catfacsts replied, pass
    # otherwise send owner message
    if len(ms) > 2:
        print('Success')
    else:
        print('Failed')
        m = groupy.object.responses.Member(user_id=owner_id)
        m.post("CatFacts Down")
        online = False

    # Destroy group, occasionally produces harmless errors but works
    try:
        g.destroy()
    except Exception as e:
        pass

    # Sleep 20 minutes until next test
    time.sleep(20*60)