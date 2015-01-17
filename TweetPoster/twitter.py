import re
from datetime import datetime

from requests_oauthlib import OAuth1

from TweetPoster import User, config, utils, sentry


import traceback


class Twitter(User):

    tweet_re = re.compile(
        r'https?://(?:www\.|mobile\.)?twitter.com/.+/status(?:es)?/([0-9]{18})'
    )

    multipart_end_re = re.compile(
        r'\S.*\((\d+)/(\d+)\)\s*$'
    )

    def __init__(self, *a, **kw):
        super(Twitter, self).__init__(*a, **kw)

        self.session.auth = OAuth1(
            config['twitter']['consumer_key'],
            config['twitter']['consumer_secret'],
            config['twitter']['access_token'],
            config['twitter']['access_secret'],
            signature_type='auth_header'
        )

    def get_tweet(self, tweet_id):
        url = 'https://api.twitter.com/1.1/statuses/show.json'
        params = {
            'id': tweet_id,
            'include_entities': 1,
        }

        r = self.get(url, params=params)
        assert r.status_code == 200, r.status_code

        return Tweet(r.json())

    def get_users_next_tweet(self, tweet_id, screen_name):
        url = 'https://api.twitter.com/1.1/statuses/user_timeline.json'
        params = {
            'count': 1,
            'since_id': tweet_id,
            'screen_name': screen_name
        }

        r = self.get(url, params=params)
        assert r.status_code == 200, r.status_code

        if (r.json()[0]):
            return Tweet(r.json()[0])
        else:
            return None


class Tweet(object):

    def __init__(self, json):
        self.user = TwitterUser(json['user'])
        self.text = json['text']
        self.plaintext = json['text']
        self.id = json['id']
        self.reply_to = None
        self.next_part = None
        self.entities = json['entities']
        self.link = 'https://twitter.com/{0}/status/{1}'.format(self.user.name, self.id)
        self.datetime = datetime.strptime(json['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
        self.markdown = utils.tweet_to_markdown(self)

        multipart_match = Twitter().multipart_end_re.match(self.plaintext)
        if multipart_match:
            print "Tweet has multiple parts"
            part_index = multipart_match.group(1)
            total_parts = multipart_match.group(2)
            if (part_index < total_parts):
                print "Attempting to get next part"
                try:
                    next_part = Twitter().get_users_next_tweet(self.id, self.user.name)
                    print "Got next part"
                    self.next_part = next_part
                except AssertionError:
                    pass
                except:
                    traceback.print_exc()
                    sentry.captureException()
        else:
            print "Single part tweet"

        if json['in_reply_to_status_id'] is not None:
            try:
                self.reply_to = Twitter().get_tweet(json['in_reply_to_status_id_str'])
            except AssertionError:
                pass
            except:
                sentry.captureException()

    def __repr__(self):
        return '<TweetPoster.twitter.Tweet ({0})>'.format(self.id)


class TwitterUser(object):

    def __init__(self, json):
        self.name = json['screen_name']
        self.link = 'https://twitter.com/' + self.name

    def __repr__(self):
        return '<TweetPoster.twitter.TwitterUser ({0})>'.format(self.name)
