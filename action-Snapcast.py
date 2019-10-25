#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paho.mqtt.client as mqtt
import json
import toml
import configparser
import uuid
import lmscontrol


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


class Squeezebox:
    def __init__(self):
        self.inject_requestids = dict()


def msg_ask_inject_names(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    err, all_names = lmsctl.get_music_names()
    if not err:
        end_session(client, data['sessionId'], "Die Namen werden zur Spracherkennung hinzugefügt.")
        operations = [('addFromVanilla', {'squeezebox_artists': all_names['artists']}),
                      ('addFromVanilla', {'squeezebox_albums': all_names['albums']}),
                      ('addFromVanilla', {'squeezebox_titles': all_names['titles']}),
                      ('addFromVanilla', {'squeezebox_playlists': all_names['playlists']}),
                      ('addFromVanilla', {'squeezebox_genres': all_names['genres']})]
        request_id = str(uuid.uuid4())
        squeezebox.inject_requestids[request_id] = data['siteId']
        mqtt_client.publish('hermes/injection/perform', json.dumps({'id': request_id,
                                                                    'operations': operations}))
    else:
        end_session(client, data['sessionId'], "Die Namen konnten nicht gesammelt werden. "
                                               "Es besteht keine Verbindung zum Medien Server.")


def msg_injection_complete(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    if data['requestId'] in squeezebox.inject_requestids:
        site_id = squeezebox.inject_requestids[data['requestId']]
        del squeezebox.inject_requestids[data['requestId']]
        notify(client, "Das Einlesen wurde erfolgreich abgeschlossen.", site_id)


def msg_ask_play_music(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))

    end_session(client, data['sessionId'])


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
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxInjectNames'), msg_ask_inject_names)
    client.message_callback_add('hermes/intent/' + add_prefix('squeezeboxMusicNew'), msg_ask_play_music)
    client.message_callback_add('hermes/injection/complete', msg_injection_complete)
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxInjectNames'))
    client.subscribe('hermes/intent/' + add_prefix('squeezeboxMusicNew'))
    client.subscribe('hermes/injection/complete')

    client.subscribe('squeezebox/answer/#')


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

    lmsctl = lmscontrol.LMSController(lms_host, lms_port)

    squeezebox = Squeezebox()

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_BROKER_ADDRESS.split(":")[0], int(MQTT_BROKER_ADDRESS.split(":")[1]))
    mqtt_client.loop_forever()
