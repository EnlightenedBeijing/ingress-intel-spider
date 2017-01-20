import logging
import time
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from ingress.ingress.models import Portal, Action, Player, MU, Message
from ingress.ingress.utils import within_range
from . import utils


_D = {
    '_': 0,
    'min_timems': 1406513783823,
}


def get_n_seconds_ago(n):
    return int(time.time() * 1000 - n * 1000)


def get_timems_last_minute():
    one_hour_ago = get_n_seconds_ago(60 * 60 * 24)
    try:
        # we must +1 for this, since sometimes a lot of items with same timestamp
        # so that we got endless loop then.
        max_timems = Action.objects.order_by('-timestamp')[0].timestamp + 1
        if one_hour_ago > max_timems:
            return one_hour_ago
        elif _D['min_timems'] > max_timems:
            return _D['min_timems']
        return max_timems
    except:
        return one_hour_ago


def get_or_create_portal(portal):
    latE6=portal['latE6']
    lngE6=portal['lngE6']
    if not within_range(latE6, lngE6):
        logging.info('found a stranger portal, ignored')
        return None

    try:
        obj_portal = Portal.objects.get(latE6=portal['latE6'],lngE6=portal['lngE6'])
        if obj_portal.team != portal['team'][0]:
            obj_portal.team = portal['team'][0]
    except Portal.DoesNotExist:
        obj_portal = Portal(
            name=portal['name'],
            team=portal['team'][0],
            latE6=portal['latE6'],
            lngE6=portal['lngE6'],
        )
    obj_portal.save()
    return obj_portal


class Command(BaseCommand):
    args = ''
    help = 'Collect Ingress Info'

    def handle(self, *args, **options):
        if utils.cookie_need_update():
            logging.error('need to update cookie and others')
            return

        _D['_'] += 1
        if _D['_'] > 8:
            return

        timems = get_timems_last_minute()
        print('==={} ({:.0f} seconds ago)'.format(timems, time.time() - (timems / 1000)))

        plexts = utils.get_plexts(timems)
        if 'result' not in plexts:
            print('Error in get_plexts()')
            print(plexts)
            return

        for item in plexts['result']:
            action = {
                'guid': item[0],
                'timestamp': item[1],
            }
            if _D['min_timems'] < item[1]:
                _D['min_timems'] = item[1]
            #if 'plext' not in item[2] \
            #        or 'markup' not in item[2]['plext']:
            #    continue
            markup = item[2]['plext']['markup']

            try:
                text = item[2]['plext']['text']
            except KeyError:
                continue

            player = {}
            portal = {}
            portal_to = {}
            resonator = 0
            is_linking = False
            is_adding_mu = False
            is_secure = False
            mu_points = 0
            player = markup[0]
            for x in markup:
                if x[0] == 'PLAYER':
                    player = {
                        'id': x[1]['plain'],
                        'team': x[1]['team'][0],
                    }
                elif x[0] == 'SECURE':
                    is_secure = True
                elif x[0] == 'SENDER':
                    player = {
                        'id': x[1]['plain'].split(':')[0],
                        'team': x[1]['team'][0],
                    }
                elif x[0] == 'PORTAL':
                    if is_linking:
                        portal_to = x[1]
                    else:
                        portal = x[1]
                elif x[0] == 'TEXT':
                    if 'plain' not in x[1]:
                        continue
                    plain = x[1]['plain']

                    if 'destroyed an' in plain:
                        action['name'] = 'destroyed'  # a resonator
                    elif 'destroyed a Control Field' in plain:
                        action['name'] = 'unfield'
                    elif 'destroyed the Link' in plain:
                        action['name'] = 'unlinked'
                    elif 'deployed an' in plain:
                        action['name'] = 'deployed'
                    elif 'captured' in plain:
                        action['name'] = 'captured'
                    elif 'created a Control' in plain:
                        action['name'] = 'field'
                    elif 'linked' in plain:
                        action['name'] = 'linked'
                    elif ' to ' == plain:
                        is_linking = True
                    elif ' +' == plain:
                        is_adding_mu = True
                    elif is_adding_mu and plain.isdigit():
                        mu_points = int(plain)
                    elif len(plain) <= 3 and 'L' in plain:
                        resonator = int(plain.strip().replace('L', ''))

            if player and not portal:
                try:
                    obj_player = Player.objects.get(id=player['id'])
                except Player.DoesNotExist:
                    obj_player = Player(**player)
                    obj_player.save()
                if not Message.objects.filter(guid=action['guid']).exists():
                    obj_message = Message(
                        guid=action['guid'],
                        text=text[:512],
                        player=player['id'],
                        team=player['team'],
                        timestamp=action['timestamp'],
                        is_secure=is_secure,
                    )
                    #obj_message.save()
                continue

            elif not player or not portal:
                continue
            elif 'name' not in action:
                action['name'] = 'unknown'
                continue

            obj_portal = get_or_create_portal(portal)
            if obj_portal is None:
                continue

            if action['name'] == 'captured':
                obj_portal.owner = player['id']
                obj_portal.capture_count += 1
                obj_portal.last_captured = now()
                # update for two cases: 1. From L0 to L1 2. From L8 to L1,
                # the portal real level will fetch inside another command.
                obj_portal.level = 1
                obj_portal.save()
            elif action['name'] == 'destroyed':
                if obj_portal.level == 8:
                    obj_portal.level -= 1
                    obj_portal.save()

            if portal_to:
                obj_portal_to = get_or_create_portal(portal_to)
            else:
                obj_portal_to = None

            action['resonator'] = resonator

            try:
                obj_player = Player.objects.get(id=player['id'])
            except Player.DoesNotExist:
                obj_player = Player(**player)
                obj_player.save()

            if action['name'] == 'deployed' and resonator >= 8:
                obj_player.over_lv8 = True
                obj_player.save()

            if not Action.objects.filter(pk=action['guid']).exists():
                action['player'] = obj_player
                action['portal'] = obj_portal
                if obj_portal_to:
                    action['portal_to'] = obj_portal_to
                Action.objects.create(**action)

            if action['name'] == 'field':
                if not MU.objects.filter(pk=action['guid']).exists():
                    obj_MU = MU(
                        guid=action['guid'],
                        player=obj_player,
                        points=mu_points,
                        timestamp=action['timestamp'],
                        team=obj_player.team
                    )
                    obj_MU.save()

            info = '{} {} {} {}'.format(player['id'], action['name'], resonator, portal['name'])
            print(info)

        ps = Portal.objects.all()
        ps = Action.objects.all()

        if len(plexts['result']) >= 50:
            self.handle(*args, **options)
