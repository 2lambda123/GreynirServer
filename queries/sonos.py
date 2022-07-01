"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    API routes
    Note: All routes ending with .api are configured not to be cached by nginx

"""

import requests
from datetime import datetime, timedelta
import flask

from util import read_api_key
from queries import query_json_api, post_to_json_api
from query import Query

import json


class SonosClient:
    def __init__(self, device_data, client_id, query=None):
        self._client_id = client_id
        self._device_data = device_data
        self._query = query
        self._sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
        self._code = self._device_data["sonos"]["credentials"]["code"]
        print("code :", self._code)
        self._timestamp = datetime.now()
        print("device data :", self._device_data)
        try:
            self._access_token = self._device_data["sonos"]["credentials"][
                "access_token"
            ]
            self._refresh_token = self._device_data["sonos"]["credentials"][
                "refresh_token"
            ]
        except KeyError:
            print("Missing credentials for sonos")
            self._create_token()
        print("continue")
        self._check_token_expiration()
        self._households = self._get_households()
        print("households :", self._households)
        self._household_id = self._households[0]["id"]
        # groups_and_players = self._get_groups_and_players()
        self._groups = self._get_groups()
        self._players = self._get_players()
        print("exited get groups")
        print(self._groups)
        self.store_sonos_data_and_credentials()

    def _check_token_expiration(self):
        try:
            timestamp = self._device_data["sonos"]["credentials"]["timestamp"]
        except KeyError:
            print("Missing timestamp for sonos access token")
            return
        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        if (datetime.now() - timestamp) > timedelta(hours=24):
            self._update_sonos_token()

    def _update_sonos_token(self):
        print("update sonos token")
        self._sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
        self._access_token = self._refresh_expired_token()
        self._access_token = self._access_token["access_token"]
        sonos_dict = {
            "sonos": {
                "credentials": {
                    "access_token": self._access_token,
                    "timestamp": str(datetime.now()),
                }
            }
        }

        self._store_data(sonos_dict)

    def _refresh_expired_token(self):
        """
        Refreshes token
        """
        print("_refresh_expired_token")
        url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=refresh_token&refresh_token={self._refresh_token}"
        headers = {"Authorization": f"Basic {self._sonos_encoded_credentials}"}

        response = post_to_json_api(url, headers=headers)

        return response

    def _create_token(self):
        """
        Creates a token given a code
        """
        print("_create_token")
        host = str(flask.request.host)
        url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=authorization_code&code={self._code}&redirect_uri=http://{host}/connect_sonos.api"
        headers = {
            "Authorization": f"Basic {self._sonos_encoded_credentials}",
            "Cookie": "JSESSIONID=F710019AF0A3B7126A8702577C883B5F; AWSELB=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171; AWSELBCORS=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171",
        }

        response = post_to_json_api(url, headers=headers)

        self._access_token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        return response

    def toggle_play_pause(self):
        """
        Toggles the play/pause of a group
        """
        print("toggle playpause")
        group_id = self._get_group_id()
        url = f"https://api.ws.sonos.com/control/api/v1/groups/{group_id}/playback/togglePlayPause"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        # response = requests.request("POST", url, headers=headers, data=payload)
        response = post_to_json_api(url, headers=headers)

        return response

    def _get_households(self):
        """
        Returns the list of households of the user
        """
        print("get households")
        try:
            print("households try")
            return self._device_data["sonos"]["data"]["households"]
        except KeyError:
            print("key error get households")
            url = f"https://api.ws.sonos.com/control/api/v1/households"
            headers = {"Authorization": f"Bearer {self._access_token}"}

            response = query_json_api(url, headers=headers)
            return response["households"]

    def _get_household_id(self):
        """
        Returns the household id for the given query
        """
        url = f"https://api.ws.sonos.com/control/api/v1/households"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = query_json_api(url, headers)

        return response["households"][0]["id"]

    def _get_groups(self):
        """
        Returns the list of groups of the user
        """
        print("get groups")
        try:
            print("try get groups")
            print("device data get groups :", self._device_data)
            return self._device_data["sonos"]["data"]["groups"]
        except KeyError:
            print("keyerror")
            for i in range(len(self._households)):
                url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
                headers = {"Authorization": f"Bearer {self._access_token}"}

                response = query_json_api(url, headers=headers)
                cleaned_groups_list = self._create_grouplist_for_db(response["groups"])
                print("cleaned_groups_list :", cleaned_groups_list)
                return cleaned_groups_list

    def get_groups_and_players(self):
        """
        Returns the list of groups of the user
        """
        print("get groups and players")

        url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        response = query_json_api(url, headers)
        return response.json()
        # return response.json()["groups"]

    def _get_group_id(self):
        """
        Returns the group id for the given query
        """
        print("get group_id")
        try:
            group_id = self._groups[0]["id"]
            return group_id
        except KeyError:
            print("_get_group_id keyerror")
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            }

            response = query_json_api(url, headers)

            return response["groups"][0]["id"]

    def _get_players(self):
        """
        Returns the list of groups of the user
        """
        print("get players")
        try:
            print("try get players")
            print("device data get players :", self._device_data)
            return self._device_data["sonos"]["data"]["players"]
        except KeyError:
            print("keyerror")
            for i in range(len(self._households)):
                url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
                headers = {"Authorization": f"Bearer {self._access_token}"}

                response = query_json_api(url, headers)
                cleaned_players_list = self._create_playerlist_for_db(
                    response["players"]
                )
                print("cleaned_groups_list :", cleaned_players_list)
                return cleaned_players_list

    def _get_player_id(self):
        """
        Returns the player id for the given query
        """
        print("get player_id")
        try:
            player_id = self._players[0]["id"]
            return player_id
        except KeyError:
            print("_get_player_id keyerror")
            url = f"https://api.ws.sonos.com/control/api/v1/households/{self._household_id}/groups"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            }

            response = query_json_api(url, headers)

            return response["players"][0]["id"]

    def _create_sonos_data_dict(self):
        print("_create_sonos_data_dict")
        data_dict = {"households": self._households}
        # groups_list = []
        # players_list = []
        for i in range(len(self._households)):
            groups_raw = self._groups
            players_raw = self._players
            # groups_list += self._create_grouplist_for_db(groups_raw)
            groups_list = self._groups
            players_list = self._players

        data_dict["groups"] = groups_list
        data_dict["players"] = players_list
        return data_dict

    def _create_sonos_cred_dict(self):
        print("_create_sonos_cred_dict")
        cred_dict = {}
        cred_dict.update(
            {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "timestamp": str(datetime.now()),
            }
        )
        return cred_dict

    def store_sonos_data_and_credentials(self):
        print("store_sonos_data_and_credentials")
        data_dict = self._create_sonos_data_dict()
        print("data dict :", data_dict)
        cred_dict = self._create_sonos_cred_dict()
        print("cred_dict :", cred_dict)
        sonos_dict = {}
        sonos_dict["sonos"] = {"credentials": cred_dict, "data": data_dict}
        print("final dict for db :", sonos_dict)
        self._store_data(sonos_dict)

    def _store_data(self, data):
        Query.store_query_data(
            self._client_id, "iot_speakers", data, update_in_place=True
        )

    def _create_grouplist_for_db(self, groups):
        print("create_grouplist_for_db")
        groups_list = []
        for i in range(len(groups)):
            groups_list.append({groups[i]["name"]: groups[i]["id"]})
        return groups_list

    def _create_playerlist_for_db(self, players):
        print("create_playerlist_for_db")
        player_list = []
        for i in range(len(players)):
            player_list.append({players[i]["name"]: players[i]["id"]})
        return player_list

    def set_credentials(self, access_token, refresh_token):
        print("set_credentials")
        self._access_token = access_token
        self._refresh_token = refresh_token
        return

    def set_data(self):
        print("set_data")
        try:
            self._households = self._get_households()
            self._household_id = self._get_household_id()
            self._groups = self._get_groups()
            self._players = self._get_players()
            self._group_id = self._get_group_id()
        except KeyError:
            print("Missing device data for this account")
        return

    def audio_clip(self, audioclip_url):
        """
        Plays an audioclip from link to .mp3 file
        """
        player_id = self._get_player_id()
        url = f"https://api.ws.sonos.com/control/api/v1/players/{player_id}/audioClip"

        payload = json.dumps(
            {
                "name": "Embla",
                "appId": "com.acme.app",
                "streamUrl": f"{audioclip_url}",
                "volume": 50,
                "priority": "HIGH",
                "clipType": "CUSTOM",
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        response = post_to_json_api(url, payload, headers)
        return response


# # TODO: Check whether this should return the ids themselves instead of the json response
# def _get_households(token):
#     """
#     Returns the list of households of the user
#     """
#     url = f"https://api.ws.sonos.com/control/api/v1/households"

#     payload = {}
#     headers = {"Authorization": f"Bearer {token}"}

#     response = requests.request("GET", url, headers=headers, data=payload)

#     return response.json()


# def _get_groups(household_id, token):
#     """
#     Returns the list of groups of the user
#     """
#     url = f"https://api.ws.sonos.com/control/api/v1/households/{household_id}/groups"

#     payload = {}
#     headers = {"Authorization": f"Bearer {token}"}

#     response = requests.request("GET", url, headers=headers, data=payload)

#     return response


# def _create_token(code, sonos_encoded_credentials, host):
#     """
#     Creates a token given a code
#     """
#     url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=authorization_code&code={code}&redirect_uri=http://{host}/connect_sonos.api"

#     payload = {}
#     headers = {
#         "Authorization": f"Basic {sonos_encoded_credentials}",
#         "Cookie": "JSESSIONID=F710019AF0A3B7126A8702577C883B5F; AWSELB=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171; AWSELBCORS=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171",
#     }

#     response = requests.request("POST", url, headers=headers, data=payload)

#     return response


# def refresh_token(sonos_encoded_credentials, refresh_token):
#     """
#     Refreshes token
#     """
#     url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=refresh_token&refresh_token={refresh_token}"

#     payload = {}
#     headers = {"Authorization": f"Basic {sonos_encoded_credentials}"}

#     response = requests.request("POST", url, headers=headers, data=payload)

#     return response


# def audio_clip(audioclip_url, player_id, token):
#     """
#     Plays an audioclip from link to .mp3 file
#     """
#     import requests
#     import json

#     url = f"https://api.ws.sonos.com/control/api/v1/players/{player_id}/audioClip"

#     payload = json.dumps(
#         {
#             "name": "Embla",
#             "appId": "com.acme.app",
#             "streamUrl": f"{audioclip_url}",
#             "volume": 50,
#             "priority": "HIGH",
#             "clipType": "CUSTOM",
#         }
#     )
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {token}",
#     }

#     response = requests.request("POST", url, headers=headers, data=payload)


# def _update_sonos_token(q, device_data):
#     print("update sonos token")
#     sonos_encoded_credentials = read_api_key("SonosEncodedCredentials")
#     refresh_token_str = device_data["sonos"]["credentials"]["refresh_token"]
#     access_token = refresh_token(sonos_encoded_credentials, refresh_token_str).json()
#     access_token = access_token["access_token"]
#     sonos_dict = {
#         "sonos": {
#             "credentials": {
#                 "access_token": access_token,
#                 "timestamp": str(datetime.now()),
#             }
#         }
#     }
#     q.set_client_data("iot_speakers", sonos_dict, update_in_place=True)
