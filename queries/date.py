"""

    Greynir: Natural language processing for Icelandic

    Date query response module

    Copyright (C) 2019 Miðeind ehf.

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


    This module is an example of a plug-in query response module
    for the Greynir query subsystem. It handles plain text queries, i.e.
    ones that do not require parsing the query text. For this purpose
    it only needs to implement the handle_plain_text() function, as
    shown below.


    This particular module handles queries related to dates.

"""

# TODO: Special days should be mentioned by name, not date, in voice answers
# TODO: Fix pronunciation of ordinal day of month (i.e. "29di" vs "29da")
# TODO: "How many weeks between April 3 and June 16?"
# TODO: Restore timezone-awareness
# TODO: "hvað er mikið eftir af vinnuvikunni", "hvað er langt í helgina"
# TODO: "Hvaða vikudagur er DAGSETNING næstkomandi?"
# TODO: "Hvað gerðist á þessum degi?"
# TODO: "Hvað eru margir dagar eftir af árinu?"
# TODO: "Hvaða vikudagur var 11. september 2001?" "Hvaða dagur er á morgun?"
# TODO: "Hvenær eru vetrarsólstöður" + more astronomical dates
# TODO: "Hvenær er dagur íslenskrar tungu" :)
# TODO: "Hvað er langt í helgina?" "Hvenær er næsti frídagur?"
# TODO: "Hvaða dagur var í gær?"
# TODO: "Hvað eru margir dagar að fram að jólum?"
# TODO: "Hvað eru margir dagar eftir af árinu? mánuðinum? vikunni?"
# TODO: "Hvenær er næst hlaupár?"
# TODO: "Hvaða árstíð er"
# TODO: "Á hvaða vikudegi er jóladagur?"
# TODO: "Hvað er langt til áramóta?"
# TODO: "hvenær er fyrsti í aðventu"
# TODO: "hvenær koma jólin"
# TODO: "hvað eru margir dagar í árinu"
# TODO: "hvítasunnan", "hvítasunnuhelgin"
# TODO: "hvenær koma jólin"
# TODO: "Hvaða öld er núna"

import json
import re
import logging
import random
from datetime import datetime, date, timedelta
from pytz import timezone

from queries import timezone4loc, gen_answer, is_plural
from settings import changedlocale


_DATE_QTYPE = "Date"


# Lemmas of keywords that could indicate that the user is trying to use this module
TOPIC_LEMMAS = [
    "dagur",
    "dagsetning",
    "mánaðardagur",
    "vikudagur",
    "vika",
    "mánuður",
    "hvítasunnudagur",
    "uppstigningardagur",
    "öskudagur",
    "hrekkjavaka",
    "fullveldisdagur",
    "sumardagur",
    "þorláksmessa",
    "aðfangadagur",
    "jól",
    "jóladagur",
    "gamlárskvöld",
    "nýársdagur",
    "baráttudagur",
    "páskar",
    "páskadagur",
    "skírdagur",
    "föstudagur",
    "þjóðhátíðardagur",
    "þjóðhátíð",
    "verslunarmannahelgi",
    "frídagur",
    "menningarnótt",
]


def help_text(lemma):
    """ Help text to return when query.py is unable to parse a query but
        one of the above lemmas is found in it """
    return "Ég get svarað ef þú spyrð til dæmis: {0}?".format(
        random.choice(
            (
                "Hvaða dagur er í dag",
                "Hvað er langt til jóla",
                "Hvenær eru páskarnir",
                "Á hvaða degi er frídagur verslunarmanna",
                "Hvenær er skírdagur",
            )
        )
    )


# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QDate

QDate →
    QDateQuery '?'?

QDateQuery →
    QDateCurrent 
    | QDateHowLongUntil 
    # | QDateHowLongSince  # Disabled for now.
    | QDateWhenIs

QDateCurrent →
    "hvað" "er" "dagsetningin" QDateNow?
    | "hver" "er" "dagsetningin" QDateNow?
    | "hvaða" "dagsetning" "er" QDateNow?
    | "hvaða" "dagur" "er" QDateNow?
    | "hvaða" "mánaðardagur" "er" QDateNow?
    | "hvaða" "vikudagur" "er" QDateNow?
    | "hver" "er" "dagurinn" QDateNow?
    | "hver" "er" "mánaðardagurinn" QDateNow?
    | "hver" "er" "vikudagurinn" QDateNow?

QDateNow →
    "í" "dag" | "núna"

QDateHowLongUntil →
    "hvað" "er" "langt" "í" QDateItem_þf
    | "hvað" "er" "langt" "fram" "að" QDateItem_þgf
    | "hvað" "er" "langt" "til" QDateItem_ef
    | "hversu" "langt" "er" "í" QDateItem_þf
    | "hversu" "langt" "er" "til" QDateItem_ef
    | "hvað" "eru" "margir" "dagar" "í" QDateItem_þf
    | "hvað" "eru" "margir" "dagar" "til" QDateItem_ef
    # | "hvað" "eru" "margar" "vikur" "í" QDateItem_þf
    # | "hvað" "eru" "margir" "mánuðir" "í" QDateItem_þf

QDateHowLongSince →
    # "hvað" "er" "langt" "síðan" QDateItem
    "hvað" "er" "langt" "um"? "liðið" "frá" QDateItem_þgf
    | "hvað" "er" "langur" "tími" "liðinn" "frá" QDateItem_þgf
    | "hvað" "eru" "margir" "dagar" "liðnir" "frá" QDateItem_þgf
    | "hvað" "eru" "margir" "mánuðir" "liðnir" "frá" QDateItem_þgf
    | "hvað" "eru" "margar" "vikur" "liðnar" "frá" QDateItem_þgf

QDateIsAre → "er" | "eru"

QDateWhenIs →
    "hvenær" QDateIsAre QDateSpecialDay_nf
    | "hvaða" "dagur" "er" QDateSpecialDay_nf
    | "á" "hvaða" "degi" QDateIsAre QDateSpecialDay_nf

QDateItem/fall →
    QDateAbsOrRel | QDateSpecialDay/fall

QDateAbsOrRel →
    FöstDagsetning | AfstæðDagsetning

# TODO: Order this by time of year
QDateSpecialDay/fall →
    QDateHalloween/fall
    | QDateWhitsun/fall
    | QDateAscensionDay/fall
    # | QDateAshDay/fall
    | QDateSovereigntyDay/fall
    # | QDateFirstDayOfSummer/fall
    | QDateThorlaksmessa/fall
    | QDateChristmasEve/fall
    | QDateChristmasDay/fall
    | QDateNewYearsEve/fall
    | QDateNewYearsDay/fall
    | QDateWorkersDay/fall
    | QDateEaster/fall
    | QDateEasterSunday/fall
    | QDateMaundyThursday/fall
    | QDateGoodFriday/fall
    | QDateNationalDay/fall
    | QDateBankHoliday/fall
    # | QDateCultureNight/fall

QDateWhitsun/fall →
    'hvítasunnudagur:kk'_et/fall

QDateAscensionDay/fall →
    'uppstigningardagur:kk'_et/fall

QDateAshDay/fall →
    'öskudagur:kk'_et/fall

QDateHalloween/fall →
    'hrekkjavaka:kvk'_et/fall

QDateSovereigntyDay/fall →
    'fullveldisdagur:kk'_et/fall

QDateFirstDayOfSummer/fall →
    'sumardagur:kk'_et_gr/fall 'fyrstur:lo'_et_kk/fall

QDateThorlaksmessa/fall →
    'þorláksmessa:kvk'_et/fall

QDateChristmasEve/fall →
    'aðfangadagur:kk'_et/fall 'jól:hk'_ef?

QDateChristmasDay/fall →
    'jól:hk'/fall 
    | 'jóladagur:kk'_et/fall

QDateNewYearsEve/fall →
    'gamlárskvöld:hk'_et/fall

QDateNewYearsDay/fall →
    'nýársdagur:kk'_et/fall

QDateWorkersDay/fall →
    'baráttudagur:kk'_et/fall 'verkalýður:kk'_et_ef

QDateEaster/fall →
    'páskar:kk'/fall

QDateEasterSunday/fall →
    'páskadagur:kk'_et/fall

QDateMaundyThursday/fall →
    'skírdagur:kk'_et/fall

QDateGoodFriday/fall →
    'föstudagur:kk'_et_gr/fall 'langur:lo'_et_kk/fall

QDateNationalDay/fall →
    'þjóðhátíðardagur:kk'_et/fall
    | 'þjóðhátíðardagur:kk'_et/fall 'Íslendingur:kk'_ft_ef
    | 'þjóðhátíðardagur:kk'_et/fall 'Ísland:hk'_et_ef
    | 'þjóðhátíð:kvk'_et/fall 'Íslendingur:kk'_ft_ef
    | 'þjóðhátíð:kvk'_et/fall 'Ísland:hk'_et_ef

QDateBankHoliday/fall →
    'verslunarmannahelgi:kvk'_et/fall
    | 'frídagur:kk'_et/fall 'verslunarmaður:kk'_ft_ef

QDateCultureNight/fall →
    'menningarnótt:kvk'_et/fall

$score(+55) QDate

"""


def QDateQuery(node, params, result):
    result.qtype = _DATE_QTYPE


def QDateCurrent(node, params, result):
    result["now"] = True


def QDateHowLongUntil(node, params, result):
    result["until"] = True


def QDateHowLongSince(node, params, result):
    result["since"] = True


def QDateWhenIs(node, params, result):
    result["when"] = True


def QDateAbsOrRel(node, params, result):
    t = result.find_descendant(t_base="dagsafs")
    if not t:
        t = result.find_descendant(t_base="dagsföst")
    if t:
        d = terminal_date(t)
        if d:
            result["target"] = d
    else:
        raise Exception("No dagsafs in {0}".format(str(t)))


def QDateWhitsun(node, params, result):
    result["desc"] = "hvítasunnudagur"
    result["target"] = next_easter() + timedelta(days=49)


def QDateAscensionDay(node, params, result):
    result["desc"] = "uppstigningardagur"
    result["target"] = next_easter() + timedelta(days=39)


def QDateAshDay(node, params, result):
    result["desc"] = "öskudagur"
    result["target"] = dnext(
        datetime(year=datetime.today().year, month=2, day=4)
    )  # Wrong


def QDateHalloween(node, params, result):
    result["desc"] = "hrekkjavaka"
    result["target"] = dnext(datetime(year=datetime.today().year, month=10, day=31))


def QDateSovereigntyDay(node, params, result):
    result["desc"] = "fullveldisdagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=1))


def QDateFirstDayOfSummer(node, params, result):
    result["desc"] = "sumardagurinn fyrsti"
    d = dnext(datetime(year=datetime.today().year, month=4, day=18))
    result["target"] = next_weekday(d, 3)


def QDateThorlaksmessa(node, params, result):
    result["desc"] = "þorláksmessa"
    d = dnext(datetime(year=datetime.today().year, month=12, day=23))


def QDateChristmasEve(node, params, result):
    result["desc"] = "aðfangadagur jóla"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=24))


def QDateChristmasDay(node, params, result):
    result["desc"] = "jóladagur"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=25))


def QDateNewYearsEve(node, params, result):
    result["desc"] = "gamlárskvöld"
    result["target"] = dnext(datetime(year=datetime.today().year, month=12, day=31))


def QDateNewYearsDay(node, params, result):
    result["desc"] = "nýársdagur"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=1, day=1))


def QDateWorkersDay(node, params, result):
    result["desc"] = "baráttudagur verkalýðsins"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=5, day=1))


def QDateEaster(node, params, result):
    result["desc"] = "páskar"
    result["is_verb"] = "eru"
    result["target"] = next_easter()


def QDateEasterSunday(node, params, result):
    result["desc"] = "páskadagur"
    result["target"] = next_easter()


def QDateGoodFriday(node, params, result):
    result["desc"] = "föstudagurinn langi"
    result["target"] = next_easter() + timedelta(days=-2)


def QDateMaundyThursday(node, params, result):
    result["desc"] = "skírdagur"
    result["target"] = next_easter() + timedelta(days=-3)


def QDateNationalDay(node, params, result):
    result["desc"] = "þjóðhátíðardagurinn"
    result["target"] = dnext(datetime(year=datetime.today().year + 1, month=6, day=17))


def QDateBankHoliday(node, params, result):
    result["desc"] = "frídagur verslunarmanna"
    # First Monday of August
    result["target"] = this_or_next_weekday(
        dnext(datetime(year=datetime.today().year + 1, month=8, day=1)), 0  # Monday
    )


def QDateCultureNight(node, params, result):
    result["desc"] = "menningarnótt"
    result["target"] = dnext(
        datetime(year=datetime.today().year + 1, month=8, day=24)
    )  # Wrong


# Day indices in nominative case
_DAY_INDEX_NOM = {
    1: "fyrsti",
    2: "annar",
    3: "þriðji",
    4: "fjórði",
    5: "fimmti",
    6: "sjötti",
    7: "sjöundi",
    8: "áttundi",
    9: "níundi",
    10: "tíundi",
    11: "ellefti",
    12: "tólfti",
    13: "þrettándi",
    14: "fjórtándi",
    15: "fimmtándi",
    16: "sextándi",
    17: "sautjándi",
    18: "átjándi",
    19: "nítjándi",
    20: "tuttugasti",
    21: "tuttugasti og fyrsti",
    22: "tuttugasti og annar",
    23: "tuttugasti og þriðji",
    24: "tuttugasti og fjórði",
    25: "tuttugasti og fimmti",
    26: "tuttugasti og sjötti",
    27: "tuttugasti og sjöundi",
    28: "tuttugasti og áttundi",
    29: "tuttugasti og níundi",
    30: "þrítugasti",
    31: "þrítugasti og fyrsti",
}


# Day indices in accusative case
_DAY_INDEX_ACC = {
    1: "fyrsta",
    2: "annan",
    3: "þriðja",
    4: "fjórða",
    5: "fimmta",
    6: "sjötta",
    7: "sjöunda",
    8: "áttunda",
    9: "níunda",
    10: "tíunda",
    11: "ellefta",
    12: "tólfta",
    13: "þrettánda",
    14: "fjórtánda",
    15: "fimmtánda",
    16: "sextánda",
    17: "sautjánda",
    18: "átjánda",
    19: "nítjánda",
    20: "tuttugasta",
    21: "tuttugasta og fyrsta",
    22: "tuttugasta og annan",
    23: "tuttugasta og þriðja",
    24: "tuttugasta og fjórða",
    25: "tuttugasta og fimmta",
    26: "tuttugasta og sjötta",
    27: "tuttugasta og sjöunda",
    28: "tuttugasta og áttunda",
    29: "tuttugasta og níunda",
    30: "þrítugasta",
    31: "þrítugasta og fyrsta",
}


# Day indices in dative case
_DAY_INDEX_DAT = _DAY_INDEX_ACC.copy()
_DAY_INDEX_DAT[2] = "öðrum"
_DAY_INDEX_DAT[22] = "tuttugasta og öðrum"


def next_weekday(d, weekday):
    """ Get the date of the next weekday after a given date.
        0 = Monday, 1 = Tuesday, 2 = Wednesday, etc. """
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def this_or_next_weekday(d, weekday):
    """ Get the date of the next weekday after or including a given date.
        0 = Monday, 1 = Tuesday, 2 = Wednesday, etc. """
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def dnext(datetime):
    """ Return datetime with year+1 if date was earlier in current year. """
    now = datetime.utcnow()
    d = datetime
    if d < now:
        d = d.replace(year=d.year + 1)
    return d


def next_easter():
    """ Find the date of next easter in the Gregorian calendar. """
    now = datetime.utcnow()
    e = calc_easter(now.year)
    if e < now:
        e = calc_easter(now.year + 1)
    return e


def calc_easter(year):
    """ An implementation of Butcher's Algorithm for determining the date of Easter 
        for the Western church. Works for any date in the Gregorian calendar (1583 
        and onward). Returns a datetime object. 
        From http://code.activestate.com/recipes/576517-calculate-easter-western-given-a-year/ """
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime(year=year, month=month, day=day)


def terminal_date(t):
    """ Extract array of date values from terminal token's auxiliary info,
        which is attached as a json-encoded array. Returns datetime object. """
    if t and t._node.aux:
        aux = json.loads(t._node.aux)
        if not isinstance(aux, list) or len(aux) < 3:
            raise Exception("Malformed token aux info")

        # Unpack date array
        (y, m, d) = aux
        if not y:
            now = datetime.utcnow()
            y = now.year
            # Bump year if month/day in the past
            if m < now.month or (m == now.month and d < now.day):
                y += 1

        return datetime(year=y, month=m, day=d)


def date_diff(d1, d2, unit="days"):
    """ Get the time difference between two dates. """
    delta = d2 - d1
    cnt = getattr(delta, unit)
    return cnt


def howlong_desc_answ(target):
    """ Generate answer to a query about length of period to a given date. """
    now = datetime.utcnow()
    days = date_diff(now, target, unit="days")

    # Diff. strings for singular vs. plural
    plural = is_plural(days)
    verb = "eru" if plural else "er"
    days_desc = "dagar" if plural else "dagur"

    # Format date
    fmt = "%-d. %B" if now.year == target.year else "%-d. %B %Y"
    tfmt = target.strftime(fmt)

    # Date asked about is current date
    if days == 0:
        return gen_answer("Það er {0} í dag.".format(tfmt))
    elif days < 0:
        # It's in the past
        days = abs(days)
        passed = "liðinn" if sing else "liðnir"
        voice = "Það {0} {1} {2} {3} frá {4}.".format(
            verb, days, days_desc, passed, tfmt
        )
        # Convert '25.' to 'tuttugasta og fimmta'
        voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_DAT[target.day] + " ", voice)
        answer = "{0} {1}".format(days, days_desc)
    else:
        # It's in the future
        voice = "Það {0} {1} {2} þar til {3} gengur í garð.".format(
            verb, days, days_desc, tfmt
        )
        # Convert '25.' to 'tuttugasti og fimmti'
        voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_NOM[target.day] + " ", voice)
        answer = "{0} {1}".format(days, days_desc)

    response = dict(answer=answer)

    return (response, answer, voice)


def sentence(state, result):
    """ Called when sentence processing is complete """
    q = state["query"]
    if "qtype" not in result:
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        with changedlocale(category="LC_TIME"):
            # Get timezone and date
            # TODO: Restore correct timezone handling
            # tz = timezone4loc(q.location, fallback="IS")
            now = datetime.utcnow()  # datetime.now(timezone(tz))
            qkey = None

            # Asking about current date
            if "now" in result:
                date_str = now.strftime("%A %-d. %B %Y")
                answer = date_str.capitalize()
                voice = "Í dag er {0}".format(date_str)
                # Put a spelled-out ordinal number instead of the numeric one
                # to get the grammar right
                voice = re.sub(r" \d+\. ", " " + _DAY_INDEX_NOM[now.day] + " ", voice)
                response = dict(answer=answer)
                qkey = "CurrentDate"
            # Asking about period until/since a given date
            elif ("until" in result or "since" in result) and "target" in result:
                target = result.target
                # target.replace(tzinfo=timezone(tz))
                # Find the number of days until target date
                (response, answer, voice) = howlong_desc_answ(target)
                qkey = "FutureDate" if "until" in result else "SinceDate"
            elif "when" in result and "target" in result:
                # TODO: Fix this so it includes weekday, e.g.
                # "Sunnudaginn 1. október"
                # Use plural 'eru' for 'páskar'
                is_verb = "er" if "is_verb" not in result else result.is_verb
                date_str = (
                    result.desc
                    + " "
                    + is_verb
                    + " "
                    + result.target.strftime("%-d. %B")
                )
                answer = voice = date_str[0].upper() + date_str[1:].lower()
                # Put a spelled-out ordinal number instead of the numeric one,
                # in accusative case
                voice = re.sub(
                    r"\d+\. ", _DAY_INDEX_ACC[result.target.day] + " ", voice
                )
                response = dict(answer=answer)
            else:
                # Shouldn't be here
                raise Exception("Unable to handle date query")

            q.set_key(qkey)
            q.set_answer(response, answer, voice)
            # Lowercase the query string to avoid 'Dagur' being
            # displayed with a capital D
            q.lowercase_beautified_query()
            q.set_qtype(_DATE_QTYPE)

    except Exception as e:
        logging.warning("Exception while processing date query: {0}".format(e))
        q.set_error("E_EXCEPTION: {0}".format(e))
