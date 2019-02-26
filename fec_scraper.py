import datetime
import json
import os
import redis
import requests
import time
import twitter


twitter_api = twitter.Api(
    consumer_key=os.environ['TWITTER_CONSUMER_KEY'],
    consumer_secret=os.environ['TWITTER_CONSUMER_SECRET'],
    access_token_key=os.environ['TWITTER_ACCESS_TOKEN_KEY'],
    access_token_secret=os.environ['TWITTER_ACCESS_TOKEN_SECRET'],
)

r = redis.Redis.from_url(os.environ['HEROKU_REDIS_IVORY_URL'])
already_posted = r.get('already_posted') or b'[]'
already_posted = json.loads(already_posted.decode('utf-8'))

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=5)
params = {
    'api_key': os.environ['FEC_KEY'],
    'election_year': '2020',
    'office': 'P',
}
url = 'https://api.open.fec.gov/v1/candidates/search/'
full_list = requests.request(
    'get',
    url,
    params=params,
)
full_count = full_list.json()['pagination']['count']
end_date_string = end_date.strftime('%Y-%m-%d')
message = f'As of {end_date_string}, {full_count} candidates have registered with the FEC to run for president in the 2020 election.'
twitter_api.PostUpdate(message)

params['max_first_file_date'] = end_date_string
params['min_first_file_date'] = start_date.strftime('%Y-%m-%d')
response = requests.request(
    'get',
    url,
    params=params,
)
data = response.json()
pagination = data['pagination']
candidates = data['results']
if pagination['pages'] > 1:
    for i in range(2, pagination['pages'] + 1):
        params['page'] = i
        response = requests.request(
            'get',
            url,
            params=params,
        )
        candidates += response.json()['results']

fh = open('parties.json', 'r')
parties = json.loads(fh.read().strip())
fh.close()
        
for candidate in candidates:
    id = candidate['candidate_id']
    if id in already_posted:
        continue
    file_date = candidate['last_file_date']
    f2_date = candidate['last_f2_date']
    if candidate['principal_committees']:
        committee = list(filter(
            lambda c: c['last_file_date'] == file_date, candidate['principal_committees']
        ))[0]['name']
    else:
        committee = None
    name = candidate['name']
    party = candidate['party']
    party_message = ''
    if party and party in parties:
        party_message = parties[party]
    message = f'On {f2_date} {name} registered to run for President{party_message}.'
    if committee:
        message += f' Their principal campaign committee is {committee}.'
    else:
        message += f' They do not have a principal compaign committee.'
    
    print(message)
    already_posted.append(id)
    twitter_api.PostUpdate(message)
    time.sleep(os.environ.get('SLEEP_TIME', 900))

r.set('already_posted', json.dumps(already_posted))
