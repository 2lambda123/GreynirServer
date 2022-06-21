from typing import Optional, cast

import logging

from query import Query, QueryStateDict
from tree import Result, Node
from queries import gen_answer, parse_num
from queries.fruit_seller.fruitstate import DialogueStateManager

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QFruit"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QFruit '?'?

QFruit →
    QFruitStartQuery | QFruitQuery

QFruitStartQuery →
    "ég" "vill" "kaupa"? "ávexti"
    | "ég" "vil" "kaupa"? "ávexti"
    | "mig" "langar" "að" "kaupa" "ávexti" "hjá"? "þér"?
    | "mig" "langar" "að" "panta" "ávexti" "hjá"? "þér"?
    | "get" "ég" "keypt" "ávexti" "hjá" "þér"

QFruitQuery →
    QAddFruitQuery
    | QRemoveFruitQuery
    | QChangeFruitQuery
    | QFruitOptionsQuery
    | QYes
    | QNo
    | QCancelOrder

QAddFruitQuery →
    "já"? "má" "ég" "fá" QFruitList
    | "já"? "get" "ég" "fengið" QFruitList
    | "já"? "gæti" "ég" "fengið" QFruitList
    | "já"? "ég" "vil" "fá" QFruitList
    | "já"? "ég" "vill" "fá" QFruitList
    | "já"? "ég" "vil" "panta" QFruitList
    | "já"? "ég" "vill" "panta" QFruitList
    | "já"? "ég" "vil" "kaupa" QFruitList
    | "já"? "ég" "vill" "kaupa" QFruitList
    | "já"? "mig" "langar" "að" "fá" QFruitList
    | "já"? "mig" "langar" "að" "kaupa" QFruitList
    | "já"? "mig" "langar" "að" "panta" QFruitList

QRemoveFruitQuery →
    "taktu" "út" QFruitList
    | "slepptu" QFruitList
    | "ég" "vil" "sleppa" QFruitList
    | "ég" "vill" "sleppa" QFruitList
    | "ég" "hætti" "við" QFruitList
    | "ég" "vil" "ekki" QFruitList
    | "ég" "vill" "ekki" QFruitList

QChangeFruitQuery →
    QChangeStart QFruitList QChangeConnector QFruitList

QChangeStart →
    "breyttu"
    | "ég" "vil" "frekar"
    | "ég" "vill" "frekar"
    | "ég" "vil" "skipta" "út"
    | "ég" "vill" "skipta" "út"
    | "ég" "vil" "breyta"
    | "ég" "vill" "breyta"

QChangeConnector →
    "en" | "í" "staðinn" "fyrir"

QFruitOptionsQuery →
    "hvað" "er" "í" "boði"
    | "hverjir" "eru" "valmöguleikarnir"
    | "hvaða" "valmöguleikar" "eru" "í" "boði" 
    | "hvaða" "valmöguleikar" "eru" "til"
    | "hvaða" "ávexti" "ertu" "með"
    | "hvaða" "ávextir" "eru" "í" "boði"

QFruitList → QNumOfFruit QNumOfFruit*

QNumOfFruit → QNum? QFruit "og"?

QNum → 'einn' | 'tveir' | 'þrír' | 'fjórir' | "fimm" | "sex" | "sjö" 
    | "átta" | "níu" | "tíu" | "ellefu" | "tólf" | "þrettán" | "fjórtán" 
    | "fimmtán" | "sextán" | "sautján" | "átján" | "nítján"

QFruit → 'banani' | 'epli' | 'pera' | 'appelsína'

QYes → "já" | "já" "takk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"?

QNo → "nei" | "nei" "takk"

QCancelOrder → "ég" "hætti" "við" 
    | "ég" "vil" "hætta" "við" "pöntunina"
    | "ég" "vill" "hætta" "við" "pöntunina" 

"""

# fruitStateManager = FruitStateManager()
_START_CONVERSATION_QTYPE = "QFruitStartQuery"
_DIALOGUE_NAME = "fruit_seller"


def QFruitStartQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = _START_CONVERSATION_QTYPE


def QAddFruitQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QAddFruitQuery"


def QRemoveFruitQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QRemoveFruitQuery"


def QCancelOrder(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QCancelOrder"


def QFruitOptionsQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QFruitOptionsQuery"


def QYes(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QYes"


def QNo(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QNo"


def QNumOfFruit(node: Node, params: QueryStateDict, result: Result):
    if "queryfruits" not in result:
        result.queryfruits = {}
    if "fruitnumber" not in result:
        result.queryfruits[result.fruit] = 1
    else:
        result.queryfruits[result.fruit] = result.fruitnumber


def QNum(node: Node, params: QueryStateDict, result: Result):
    fruitnumber = int(parse_num(node, result._nominative))
    if fruitnumber is not None:
        result.fruitnumber = fruitnumber
    else:
        result.fruitnumber = 1


def QFruit(node: Node, params: QueryStateDict, result: Result):
    fruit = result._root
    if fruit is not None:
        result.fruit = fruit


def updateClientData(query: Query, fruitStateManager: DialogueStateManager):
    query.set_client_data(
        _DIALOGUE_NAME, {"state": DialogueStateManager.serialize(fruitStateManager)}
    )


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dialogue_state = q.get_dialogue_state() or {}
    qt = result.get("qtype")

    # checka hvort user se i samtali med q.client_data
    if qt != _START_CONVERSATION_QTYPE and not (
        dialogue_state and dialogue_state.get("in_dialogue") == _DIALOGUE_NAME
    ):
        print("User not in dialogue")
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        print("Qtypy: ", result.qtype)
        if result.qtype == _START_CONVERSATION_QTYPE:
            fruitStateManager = DialogueStateManager()
            fruitStateManager.initialize_resources(_START_CONVERSATION_QTYPE)
            q.start_dialogue(
                _DIALOGUE_NAME, DialogueStateManager.serialize(fruitStateManager)
            )
        else:
            if dialogue_state is None:
                print("Dialogue state is none")
                q.set_error("E_QUERY_NOT_UNDERSTOOD")
                return
            print(dialogue_state)
            fruitmanager_serialized: Optional[str] = cast(
                Optional[str], dialogue_state.get("state")
            )
            if not fruitmanager_serialized:
                print("Fruitmanager not serialized")
                q.set_error("E_QUERY_NOT_UNDERSTOOD")
                return
            fruitStateManager = DialogueStateManager.deserialize(
                fruitmanager_serialized
            )
            fruitStateManager.stateMethod(result.qtype, result)

        updateClientData(q, fruitStateManager)
        ans = fruitStateManager.ans

        if result.qtype == "OrderComplete" or result.qtype == "CancelOrder":
            q.end_dialogue()

        q.set_answer(*gen_answer(ans))
        return
    except Exception as e:
        logging.warning(
            "Exception {0} while processing fruit seller query '{1}'".format(e, q.query)
        )
        q.set_error("E_EXCEPTION: {0}".format(e))
