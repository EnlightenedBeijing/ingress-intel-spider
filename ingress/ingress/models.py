from urllib.parse import quote
import datetime
from django.db import models
from django.utils.timezone import now
import uuid


class Portal(models.Model):
    guid = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name = models.CharField(max_length=256)
    team = models.CharField(max_length=1, db_index=True)
    owner = models.CharField(max_length=40, blank=True)
    latE6 = models.IntegerField()
    lngE6 = models.IntegerField()
    rlat = models.CharField(max_length=24, default='')
    rlng = models.CharField(max_length=24, default='')
    has_maps = models.BooleanField(default=False)

    level = models.IntegerField(default=0)
    image = models.CharField(max_length=255, default='')
    image_fetched = models.BooleanField(default=False)

    mod_status = models.CharField(max_length=512, default='')
    res_count = models.IntegerField(default=0)
    res_status = models.CharField(max_length=512, default='')
    health = models.IntegerField(default=0)
    updated = models.DateTimeField(null=True)

    last_captured = models.DateTimeField(null=True)
    capture_count = models.IntegerField(default=0)
    has_problem = models.BooleanField(default=False)

    added = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return '/portals/{}/'.format(self.guid)

    def get_ingress_url(self):
        url = 'http://www.ingress.com/intel?latE6={}&lngE6={}&z=17'
        return url.format(self.latE6, self.lngE6)

    def get_actions_url(self):
        url = '/actions/portal/{}/'
        return url.format(self.guid)

    def get_baidu_map_url(self):
        url = 'http://api.map.baidu.com/marker' \
              '?location={},{}&title={}&content={}&output=html'
        return url.format(self.rlat, self.rlng,
            quote(self.name), self.owner)

    def get_baidu_map_url_for_ios(self):
        url = 'baidumap://map/marker' \
              '?location={},{}&title={}&content={}'
        return url.format(self.rlat, self.rlng,
            quote(self.name), self.owner)

    def get_hold_days(self):
        if not self.last_captured:
            return 'Unknown'
        return (now() - self.last_captured).days

    def mod_list(self):
        result = []
        for s in self.mod_status.split('|'):
            if not s:
                break
            name, rarity, owner = s.split('+')
            result.append({
                'name': name,
                'rarity': rarity.replace(' ', '_'),
                'owner': owner,
            })
        while len(result) < 4:
            result.append({'rarity': 'empty'})
        return result

    def resolator_list(self):
        result = []
        for s in self.res_status.split('|'):
            if not s:
                break
            level, owner, _ = s.split('+')
            result.append({
                'level': level,
                'owner': owner,
            })
        while len(result) < 8:
            result.append({'team': 'empty'})
        return result

    def get_lat(self):
        return '{:.6f}'.format(self.latE6 / 1000000)

    def get_lng(self):
        return '{:.6f}'.format(self.lngE6 / 1000000)

    def get_cn_lat(self):
        if not self.rlat:
            return ''
        return '{:.6f}'.format(float(self.rlat))

    def get_cn_lng(self):
        if not self.rlng:
            return ''
        return '{:.6f}'.format(float(self.rlng))

    def updated_str(self):
        if not self.updated:
            return "NEVER"

        span =  now() - self.updated
        days = span.days
        seconds = span.seconds
        if days >= 6:
            return self.updated.strftime('%Y-%m-%d')
        elif days > 1:
            return '{} days ago'.format(days)
        elif days == 1:
            return '1 day ago'
        elif seconds >= 3600 * 2:
            return '{} hours ago'.format(seconds // 3600)
        elif seconds >= 3600:
            return '1 hour ago'
        elif seconds >= 60 * 2:
            return '{} mins ago'.format(seconds // 60)
        elif seconds >= 60:
            return '1 min ago'
        elif seconds > 1:
            return '{} secs ago'.format(seconds)
        else:
            return '1 sec ago'


class Player(models.Model):
    id = models.CharField(max_length=40, primary_key=True)
    team = models.CharField(max_length=1, db_index=True)
    portal_count = models.IntegerField(default=0)
    over_lv8 = models.BooleanField(default=False)
    added = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.id

    @staticmethod
    def get_team(pid):
        try:
            p = Player.objects.get(id=pid)
            return p.team
        except Player.DoesNotExist:
            return 'N'


class Action(models.Model):
    guid = models.CharField(max_length=64, primary_key=True)
    player = models.ForeignKey('Player')
    name = models.CharField(max_length=40)
    resonator = models.IntegerField(default=0)
    portal = models.ForeignKey('Portal', null=True, blank=True, related_name='portal')
    portal_to = models.ForeignKey('Portal', null=True, blank=True, related_name='portal_to')
    timestamp = models.BigIntegerField()
    added = models.DateTimeField(auto_now_add=True, db_index=True)

    def hour_minute(self):
        d = datetime.datetime.utcfromtimestamp(self.timestamp // 1000)
        span =  now().replace(tzinfo=None) - d
        days = span.days
        seconds = span.seconds
        if days >= 7:
            return d.strftime('%Y-%m-%d')
        elif days > 1:
            return '{} days ago'.format(days)
        elif days == 1:
            return '1 day ago'
        elif seconds >= 3600 * 2:
            return '{} hours ago'.format(seconds // 3600)
        elif seconds >= 3600:
            return '1 hour ago'
        elif seconds >= 60 * 2:
            return '{} mins ago'.format(seconds // 60)
        elif seconds >= 60:
            return '1 min ago'
        elif seconds > 1:
            return '{} secs ago'.format(seconds)
        else:
            return '1 sec ago'


class MU(models.Model):
    guid = models.CharField(max_length=64, primary_key=True)
    player = models.ForeignKey('Player')
    points = models.BigIntegerField()
    timestamp = models.BigIntegerField()
    team = models.CharField(max_length=1, db_index=True)
    added = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    guid = models.CharField(max_length=64, primary_key=True)
    text = models.CharField(max_length=512)
    player = models.CharField(max_length=40, blank=True)
    team = models.CharField(max_length=1)
    timestamp = models.BigIntegerField()
    is_secure = models.BooleanField(default=False)
    added = models.DateTimeField(auto_now_add=True)

    def get_text(self):
        return ':'.join(self.text.split(':')[1:]).strip()

    def get_time(self):
        d = datetime.datetime.utcfromtimestamp(self.timestamp // 1000)
        span =  now().replace(tzinfo=None) - d
        days = span.days
        seconds = span.seconds
        if days >= 7:
            return d.strftime('%Y-%m-%d')
        elif days > 1:
            return '{} days ago'.format(days)
        elif days == 1:
            return '1 day ago'
        elif seconds >= 3600 * 2:
            return '{} hours ago'.format(seconds // 3600)
        elif seconds >= 3600:
            return '1 hour ago'
        elif seconds >= 60 * 2:
            return '{} mins ago'.format(seconds // 60)
        elif seconds >= 60:
            return '1 min ago'
        elif seconds > 1:
            return '{} secs ago'.format(seconds)
        else:
            return '1 sec ago'


class Account(models.Model):
    id = models.AutoField(primary_key=True)
    google_username = models.CharField(max_length=64, blank=True, unique=True)
    google_password = models.CharField(max_length=64, blank=True)
    ingress_SACSID = models.CharField(max_length=1024)
    ingress_csrf_token = models.CharField(max_length=1024)
    ingress_payload_v = models.CharField(max_length=64,blank=True)
    is_valid = models.BooleanField(default=False)

    def __str__(self):
        return self.google_username
