"""

    Greynir: Natural language processing for Icelandic

    Randomness query response module

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

    This query module handles queries related to the generation
    of random numbers, e.g. "Kastaðu tengingi", "Nefndu tölu milli 5 og 10", etc.

"""

from typing import Dict, Mapping, Optional, cast

import logging
import random

from query import Query, QueryStateDict, AnswerTuple
from queries import gen_answer
from tree import Result, Node


_IoT_QTYPE = "IoT"

TOPIC_LEMMAS = ["ljós", "kveikja"]


def help_text(lemma: str) -> str:
    """Help text to return when query.py is unable to parse a query but
    one of the above lemmas is found in it"""
    return "Ég skil þig ef þú segir til dæmis: {0}.".format(
        random.choice(
            (
                "Kastaðu teningi",
                "Kastaðu tíu hliða teningi",
                "Fiskur eða skjaldarmerki",
                "Kastaðu teningi",
                "Kastaðu peningi",
                "Veldu tölu á milli sjö og þrettán",
            )
        )
    )


_COLORS = {
    "gulur": [],
    "rauður": [],
    "grænn": [],
    "blár": [],
    "hvítur": [],
    "fjólublár": [],
    "brúnn": [],
    "bleikur": [],
    "appelsínugulur": [],
    "rauður": [],
}


# This module wants to handle parse trees for queries
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QIoT"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = f"""

Query →
    QIoT

QIoT → QIoTQuery '?'?

QIoTQuery →
    QIoTTurnOn | QIoTTurnOff | QIoTSetColor | QIoTIncreaseBrightness | QIoTDecreaseBrightness

QIoTTurnOn ->
    "kveiktu" QIoTLightPhrase

QIoTTurnOff ->
    "slökktu" QIoTLightPhrase 

QIoTSetColor ->
    "gerðu" QIoTColorLightPhrase QIoTColorNamePhrase
    | "gerðu" QIoTLight QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "gerðu" QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "breyttu" QIoTColorLightPhrase í QIoTColorNamePhrase
    | "breyttu" QIoTColorLight í QIoTColorNamePhrase QIoTGroupNamePhrase?
    | "settu" QIoTColorNamePhrase QIoTColorLightPhrase
    

QIoTIncreaseBrightness ->
    QIoTIncrease QIoTBrightness QIoTLightPhrase?
    | "gerðu" QIoTLightPhrase  "bjartara"

QIoTDecreaseBrightness ->
    QIoTDecrease QIoTBrightness QIoTLightPhrase?
    | "gerðu" QIoTLightPhrase "bjartara"

QIoTIncrease ->
    "hækkaðu"
    | "auktu"

QIoTDecrease ->
    "lækkaðu"
    | "minnkaðu"

QIoTBrightness ->
    "birtu" | "birtustig" | "birtuna" | "birtustigið"

QIoTColorLightPhrase ->
    QIoTColorLight QIoTGroupNamePhrase?

QIoTColorLight ->
    QIoTColor? "á"? "í"? QIoTLight
    | QIoTColor

QIoTLightPhrase ->
    "á"? "í"? QIoTLight QIoTGroupNamePhrase?
    | "á"? "í"? QIoTGroupNamePhrase

# tried making this 'ljós:no' to avoid ambiguity, but all queries failed as a result
QIoTLight ->
    'ljós'

QIoTColor ->
    'litur'

QIoTColorName ->
    {" | ".join(f"'{color}:lo'" for color in _COLORS.keys())}

QIoTColorNamePhrase ->
    QIoTColor? QIoTColorName
    | QIoTColorName QIoTColor?

QIoTGroupNamePhrase ->
    "í" QIoTGroupName
    | "á" QIoTGroupName

QIoTGroupName ->
    Nl

"""


def QIoTQuery(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = _IoT_QTYPE


def QIoTTurnOn(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_off"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": True}
    else:
        result["hue_obj"]["on"] = True


def QIoTTurnOff(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "turn_on"
    if "hue_obj" not in result:
        result["hue_obj"] = {"on": False}
    else:
        result["hue_obj"]["on"] = False


def QIoTSetColor(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "set_color"
    color_hue = _COLOR_NAME_TO_CIE.get(result.color_name, None)
    if color_hue is not None:
        if "hue_obj" not in result:
            result["hue_obj"] = {"hue": color_hue}
        else:
            result["hue_obj"]["hue"] = color_hue


def QIoTIncreaseBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "increase_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": 64}
    else:
        result["hue_obj"]["bri_inc"] = 64


def QIoTDecreaseBrightness(node: Node, params: QueryStateDict, result: Result) -> None:
    result.action = "decrease_brightness"
    if "hue_obj" not in result:
        result["hue_obj"] = {"bri_inc": -64}
    else:
        result["hue_obj"]["bri_inc"] = -64


def QIoTColorName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["color_name"] = result._indefinite


def QIoTGroupName(node: Node, params: QueryStateDict, result: Result) -> None:
    result["group_name"] = result._indefinite


# Convert color name into hue
# Taken from home.py
_COLOR_NAME_TO_CIE: Mapping[str, float] = {
    "gulur": 60 * 65535 / 360,
    "grænn": 120 * 65535 / 360,
    "ljósblár": 180 * 65535 / 360,
    "blár": 240 * 65535 / 360,
    "bleikur": 300 * 65535 / 360,
    "rauður": 360 * 65535 / 360,
}


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    q.set_qtype(result.qtype)

    try:
        # kalla í javascripts stuff
        group_name = result.get("group_name", "")
        color_name = result.get("color_name", "")
        print("GROUP NAME:", group_name)
        print("COLOR NAME:", color_name)
        print(result.hue_obj)
        q.set_answer(
            *gen_answer(
                "ég var að kveikja ljósin! "
                + group_name
                + " "
                + color_name
                + " "
                + result.action
                + " "
                + str(result.hue_obj.get("hue", "enginn litur"))
            )
        )
    except Exception as e:
        logging.warning("Exception while processing random query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
        raise
