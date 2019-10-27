#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
import toml
import configparser
import uuid
import lmscontroller


USERNAME_INTENTS = "domi"
MQTT_BROKER_ADDRESS = "localhost:1883"
MQTT_USERNAME = None
MQTT_PASSWORD = None


def add_prefix(intent_name):
    return USERNAME_INTENTS + ":" + intent_name


def read_configuration_file(configuration_file):
    try:
        cp = configparser.ConfigParser()
        with open(configuration_file, encoding="utf-8") as f:
            cp.read_file(f)
        return {section: {option_name: option for option_name, option in cp.items(section)}
                for section in cp.sections()}
    except (IOError, configparser.Error):
        return dict()


def get_slots(data):
    slot_dict = {}
    try:
        for slot in data['slots']:
            if slot['value']['kind'] in ["InstantTime", "TimeInterval", "Duration"]:
                slot_dict[slot['slotName']] = slot['value']
            elif slot['value']['kind'] in ["Custom", "Number"]:
                slot_dict[slot['slotName']] = slot['value']['value']
    except (KeyError, TypeError, ValueError):
        slot_dict = {}
    return slot_dict


class Squeezebox:
    def __init__(self):
        self.inject_requestids = dict()


def msg_result_site_info(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if not lmsctl.sites_dict.get(data['site_id']):
        lmsctl.sites_dict[data['site_id']] = lmscontroller.Site()
    lmsctl.sites_dict[data['site_id']].update(data, lmsctl.server)


def msg_inject_names(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    end_session(client, data['sessionId'])

    all_site_names = lmsctl.get_all_site_names()
    err, all_music_names = lmsctl.get_music_names()
    if err:
        text = "Die Namen konnten nicht gesammelt werden. Es besteht keine Verbindung zum Medien Server."
        notify(client, text, data['siteId'])
        return

    operations = [('addFromVanilla', {'squeezebox_artists': all_music_names['artists']}),
                  ('addFromVanilla', {'squeezebox_albums': all_music_names['albums']}),
                  ('addFromVanilla', {'squeezebox_titles': all_music_names['titles']}),
                  ('addFromVanilla', {'squeezebox_playlists': all_music_names['playlists']}),
                  ('addFromVanilla', {'squeezebox_genres': all_music_names['genres']}),
                  ('addFromVanilla', {'audio_devices': all_site_names['devices']}),
                  ('addFromVanilla', {'squeezebox_rooms': all_site_names['rooms']}),
                  ('addFromVanilla', {'squeezebox_areas': all_site_names['areas']})]
    request_id = str(uuid.uuid4())
    squeezebox.inject_requestids[request_id] = data['siteId']
    payload = {'id': request_id, 'operations': operations}
    mqtt_client.publish('hermes/injection/perform', json.dumps(payload))


def msg_injection_complete(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if data['requestId'] in squeezebox.inject_requestids:
        site_id = squeezebox.inject_requestids[data['requestId']]
        del squeezebox.inject_requestids[data['requestId']]
        notify(client, "Das Einlesen wurde erfolgreich abgeschlossen.", site_id)


def msg_music_new(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    slot_dict = get_slots(data)
    err = lmsctl.new_music(slot_dict, data['siteId'])
    end_session(client, data['sessionId'], err)


def msg_result_device_connect(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))

    err, site = lmsctl.get_site(data['siteId'])
    if err:
        return err

    if site.pending_action and data['result']:
        if site.pending_action['action'] == "new_music":
            slot_dict = site.pending_action['slot_dict']
            request_siteid = site.pending_action['request_siteid']
            err = lmsctl.new_music(slot_dict, request_siteid)
            if err:
                notify(mqtt_client, err, request_siteid)

    elif site.pending_action and not data['result']:
        request_siteid = site.pending_action['request_siteid']
        site.pending_action = None
        notify(mqtt_client, "Das Gerät konnte nicht verbunden werden.", request_siteid)


def session_started_received(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    err, site = lmsctl.get_site(data['siteId'])
    if err or not site.auto_pause:
        return
    for device_mac in site.devices_dict:
        d = site.devices_dict[device_mac]
        if d.player and d.player.mode == "play":
            d.auto_pause = True
            d.player.pause()


def session_ended_received(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    err, site = lmsctl.get_site(data['siteId'])
    if err:
        return
    for device_mac in site.devices_dict:
        d = site.devices_dict[device_mac]
        if d.player and d.player.mode == "pause" and d.auto_pause:
            d.auto_pause = False
            d.player.play(1.1)


def msg_music_pause(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    lmsctl.pause_music(get_slots(data), data['siteId'])
    end_session(client, data['sessionId'])


def msg_music_play(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    lmsctl.play_music(get_slots(data), data['siteId'])
    end_session(client, data['sessionId'])


def msg_volume_change(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    lmsctl.change_volume(get_slots(data), data['siteId'])
    end_session(client, data['sessionId'])


def end_session(client, session_id, text=None):
    if text:
        payload = {'text': text, 'sessionId': session_id}
    else:
        payload = {'sessionId': session_id}
    client.publish('hermes/dialogueManager/endSession', json.dumps(payload))


def notify(client, text, site_id):
    data = {'type': 'notification', 'text': text}
    if site_id:
        payload = {'siteId': site_id, 'init': data}
    else:
        payload = {'init': data}
    client.publish('hermes/dialogueManager/startSession', json.dumps(payload))


def inject(client, entity_name, values, request_id, operation_kind='add'):
    operation = (operation_kind, {entity_name: values})
    client.publish('hermes/injection/perform', json.dumps({'id': request_id, 'operations': [operation]}))


def dialogue(client, session_id, text, intent_filter, custom_data=None):
    data = {'text': text,
            'sessionId': session_id,
            'intentFilter': intent_filter}
    if custom_data:
        data['customData'] = json.dumps(custom_data)
    client.publish('hermes/dialogueManager/continueSession', json.dumps(data))


def on_connect(client, userdata, flags, rc):
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxInjectNames'), msg_inject_names)
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxMusicNew'), msg_music_new)
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxMusicPause'), msg_music_pause)
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxMusicPlay'), msg_music_play)
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxVolumeChange'), msg_volume_change)
    client.message_callback_add('hermes/injection/complete', msg_injection_complete)
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxInjectNames'))
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxMusicNew'))
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxMusicPause'))
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxMusicPlay'))
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxVolumeChange'))
    client.subscribe('hermes/injection/complete')

    client.message_callback_add('squeezebox/answer/siteInfo', msg_result_site_info)
    client.subscribe('squeezebox/answer/#')

    client.message_callback_add('squeezebox/answer/deviceConnect', msg_result_device_connect)
    client.subscribe('squeezebox/answer/deviceConnect')

    client.message_callback_add('hermes/dialogueManager/sessionStarted', session_started_received)
    client.message_callback_add('hermes/dialogueManager/sessionEnded', session_ended_received)
    client.subscribe('hermes/dialogueManager/sessionStarted')
    client.subscribe('hermes/dialogueManager/sessionEnded')


if __name__ == "__main__":
    snips_config = toml.load('/etc/snips.toml')
    if 'mqtt' in snips_config['snips-common'].keys():
        MQTT_BROKER_ADDRESS = snips_config['snips-common']['mqtt']
    if 'mqtt_username' in snips_config['snips-common'].keys():
        MQTT_USERNAME = snips_config['snips-common']['mqtt_username']
    if 'mqtt_password' in snips_config['snips-common'].keys():
        MQTT_PASSWORD = snips_config['snips-common']['mqtt_password']

    config = read_configuration_file('config.ini')

    if config['secret'].get('lms_api_location'):
        lms_location = config['secret'].get('lms_api_location').split(":")
        lms_host = lms_location[0]
        lms_port = int(lms_location[1])
    else:
        lms_host = "localhost"
        lms_port = 9000

    squeezebox = Squeezebox()

    mqtt_client = mqtt.Client()

    lmsctl = lmscontroller.LMSController(mqtt_client, lms_host, lms_port)

    mqtt_client.on_connect = on_connect
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_BROKER_ADDRESS.split(":")[0], int(MQTT_BROKER_ADDRESS.split(":")[1]))
    mqtt_client.publish('squeezebox/request/allSites/siteInfo')
    mqtt_client.loop_forever()
