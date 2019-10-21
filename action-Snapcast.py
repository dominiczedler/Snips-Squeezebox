#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
import toml
import configparser
import threading
import time


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
            elif slot['value']['kind'] == "Custom":
                slot_dict[slot['slotName']] = slot['value']['value']
    except (KeyError, TypeError, ValueError) as e:
        print("Error: ", e)
        slot_dict = {}
    return slot_dict


def get_site_info(slot_dict, request_siteid):
    site_info = {'err': None, 'room_name': None, 'site_id': None}
    if 'room' in slot_dict:
        if request_siteid in snapcast.site_info and \
                slot_dict['room'] == snapcast.site_info[request_siteid]['room_name'] \
                or slot_dict['room'] == "hier":
            site_info['site_id'] = request_siteid
        elif request_siteid in snapcast.site_info and \
                slot_dict['room'] != snapcast.site_info[request_siteid]['room_name']:
            dict_rooms = {snapcast.site_info[siteid]['room_name']: siteid for siteid in snapcast.site_info}
            site_info['site_id'] = dict_rooms[slot_dict['room']]
        else:
            site_info['err'] = f"Der Raum {slot_dict['room']} wurde noch nicht konfiguriert."
    else:
        site_info['site_id'] = request_siteid
    if 'room_name' in snapcast.site_info[site_info['site_id']]:
        site_info['room_name'] = snapcast.site_info[site_info['site_id']]['room_name']
    else:
        site_info['err'] = f"Der Raum {slot_dict['room']} wurde noch nicht konfiguriert."
    return site_info


class Snapcast:
    def __init__(self):
        self.site_info = dict()
        self.site_music = dict()
        self.request_siteid = None
        self.threadobj_injection = None


def thread_delayed_music_injection():
    time.sleep(3)
    artists = set()
    albums = set()
    titles = set()
    genres = set()
    for site_id in snapcast.site_music:
        for artist in snapcast.site_music[site_id]['artists']:
            artists.add(artist)
        for album in snapcast.site_music[site_id]['albums']:
            albums.add(album)
        for title in snapcast.site_music[site_id]['titles']:
            titles.add(title)
        for genre in snapcast.site_music[site_id]['genres']:
            genres.add(genre)
    operations = [('addFromVanilla', {'snapcast_artists': list(artists)}),
                  ('addFromVanilla', {'snapcast_albums': list(albums)}),
                  ('addFromVanilla', {'snapcast_titles': list(titles)}),
                  ('addFromVanilla', {'snapcast_genres': list(genres)})]
    mqtt_client.publish('hermes/injection/perform', json.dumps({'id': snapcast.request_siteid,
                                                                'operations': operations}))
    snapcast.site_music = dict()


def msg_ask_inject_devices(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    snapcast.request_siteid = data['siteId']
    end_session(client, data['sessionId'], "Die Gerätenamen werden zur Spracherkennung hinzugefügt.")
    device_names = set()
    for site_id in snapcast.site_info:
        for device in snapcast.site_info[site_id]['devices']:
            for name in device['names_list']:
                device_names.add(name)
    inject(client, 'audio_devices', list(device_names), snapcast.request_siteid, 'addFromVanilla')


def msg_result_site_info(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    snapcast.site_info[data['site_id']] = data


def msg_ask_inject_music(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    snapcast.request_siteid = data['siteId']
    client.publish('snapcast/request/allSites/siteMusic')
    end_session(client, data['sessionId'], "Die Musik wird zur Spracherkennung hinzugefügt.")


def msg_result_site_music(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if not snapcast.site_music:
        snapcast.threadobj_injection = threading.Thread(target=thread_delayed_music_injection)
        snapcast.threadobj_injection.start()
    snapcast.site_music[data['site_id']] = data


def msg_injection_complete(client, userdata, msg):
    # TODO: Make requestId -> UUID; the SiteId must be saved
    data = json.loads(msg.payload.decode("utf-8"))
    notify(client, "Das Einlesen wurde erfolgreich abgeschlossen.", data['requestId'])


def msg_ask_play_music(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    site_info = get_site_info(get_slots(data), data['siteId'])
    if site_info['err']:
        end_session(client, data['sessionId'], site_info['err'])
        return
    client.publish(f'snapcast/request/oneSite/{site_info["site_id"]}/playMusic', json.dumps(get_slots(data)))
    end_session(client, data['sessionId'])


def msg_result_play_music(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    notify(client, data['err'], data['site_id'])


def end_session(client, session_id, text=None):
    if text:
        data = {'text': text, 'sessionId': session_id}
    else:
        data = {'sessionId': session_id}
    client.publish('hermes/dialogueManager/endSession', json.dumps(data))


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
    client.message_callback_add('hermes/intent/' + add_prefix('snapcastInjectDevices'), msg_ask_inject_devices)
    client.message_callback_add('hermes/intent/' + add_prefix('snapcastInjectMusic'), msg_ask_inject_music)
    client.message_callback_add('hermes/intent/' + add_prefix('snapcastMusicPlay'), msg_ask_play_music)
    client.message_callback_add('hermes/injection/complete', msg_injection_complete)
    client.subscribe('hermes/intent/' + add_prefix('snapcastInjectDevices'))
    client.subscribe('hermes/intent/' + add_prefix('snapcastInjectMusic'))
    client.subscribe('hermes/intent/' + add_prefix('snapcastMusicPlay'))
    client.subscribe('hermes/injection/complete')

    client.message_callback_add('snapcast/answer/siteInfo', msg_result_site_info)
    client.message_callback_add('snapcast/answer/siteMusic', msg_result_site_music)
    client.message_callback_add('snapcast/answer/playMusic', msg_result_play_music)
    client.subscribe('snapcast/answer/#')


if __name__ == "__main__":
    snips_config = toml.load('/etc/snips.toml')
    if 'mqtt' in snips_config['snips-common'].keys():
        MQTT_BROKER_ADDRESS = snips_config['snips-common']['mqtt']
    if 'mqtt_username' in snips_config['snips-common'].keys():
        MQTT_USERNAME = snips_config['snips-common']['mqtt_username']
    if 'mqtt_password' in snips_config['snips-common'].keys():
        MQTT_PASSWORD = snips_config['snips-common']['mqtt_password']

    config = read_configuration_file('config.ini')
    snapcast = Snapcast()

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_BROKER_ADDRESS.split(":")[0], int(MQTT_BROKER_ADDRESS.split(":")[1]))
    mqtt_client.publish('snapcast/request/allSites/siteInfo')
    mqtt_client.loop_forever()
